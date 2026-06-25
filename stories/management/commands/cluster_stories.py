from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from aiproviders.config import effective_config
from articles.models import Article
from stories.models import Story, StoryArticle
from stories.similarity import cosine, mean_vector


class Command(BaseCommand):
    help = "Agrupa artículos nuevos en historias por similitud de embeddings (incremental, por usuario)."

    def add_arguments(self, parser):
        parser.add_argument("--user", help="limitar a un username")

    def handle(self, *args, **opts):
        User = get_user_model()
        users = User.objects.all()
        if opts.get("user"):
            users = users.filter(username=opts["user"])

        total_assigned, total_new_stories = 0, 0
        for user in users:
            cfg = effective_config(user)
            since = timezone.now() - timedelta(days=cfg["cluster_window_days"])
            assigned, new_stories = self._cluster_user(user, since, cfg["cluster_threshold"])
            total_assigned += assigned
            total_new_stories += new_stories
        self.stdout.write(
            self.style.SUCCESS(
                f"Artículos asignados: {total_assigned} | historias nuevas: {total_new_stories}"
            )
        )

    def _cluster_user(self, user, since, threshold):
        from django.db import connection

        # Artículos del usuario, con embedding, no asignados todavía.
        unassigned = list(
            Article.objects.filter(
                feed__user=user, embedding__isnull=False, stories__isnull=True
            ).select_related("source").order_by("published_at", "id")
        )
        if not unassigned:
            return 0, 0
        # En Postgres usamos pgvector (vecino más cercano por ANN, en C) en vez del coseno
        # en Python O(n²): mucho más rápido para reagrupar miles de artículos.
        if connection.vendor == "postgresql":
            return self._cluster_pgvector(user, unassigned, threshold)
        return self._cluster_python(user, unassigned, since, threshold)

    def _new_story(self, user, article):
        story = Story.objects.create(
            user=user, headline=article.title[:500], centroid=article.embedding, dirty=True
        )
        StoryArticle.objects.create(story=story, article=article, similarity=1.0)
        return story

    def _cluster_pgvector(self, user, unassigned, threshold):
        """Por cada artículo, busca el YA asignado más cercano (pgvector). Único toque a vistas."""
        from pgvector.django import CosineDistance

        assigned, new_stories = 0, 0
        for article in unassigned:
            nearest = (
                Article.objects.filter(
                    feed__user=user, stories__isnull=False, embedding_vec__isnull=False
                )
                .annotate(_d=CosineDistance("embedding_vec", article.embedding))
                .order_by("_d").values("id", "_d").first()
            )
            if nearest is not None and (1 - nearest["_d"]) >= threshold:
                sa = (StoryArticle.objects.filter(article_id=nearest["id"], story__user=user)
                      .select_related("story").first())
                StoryArticle.objects.create(story=sa.story, article=article, similarity=1 - nearest["_d"])
                sa.story.dirty = True
                sa.story.save(update_fields=["dirty", "last_updated"])
            else:
                self._new_story(user, article)
                new_stories += 1
            assigned += 1
        return assigned, new_stories

    def _cluster_python(self, user, unassigned, since, threshold):
        """Fallback (SQLite/dev): coseno en Python contra los centroides de las historias."""
        candidates = list(
            Story.objects.filter(user=user, last_updated__gte=since).exclude(centroid__isnull=True)
        )
        # Una historia agrupa por TEMA (mismo suceso a lo largo del tiempo), permitiendo
        # varios artículos de la misma fuente: así el timeline muestra la evolución completa.
        assigned, new_stories = 0, 0
        for article in unassigned:
            best_story, best_sim = None, 0.0
            for story in candidates:
                sim = cosine(article.embedding, story.centroid)
                if sim > best_sim:
                    best_story, best_sim = story, sim

            if best_story is not None and best_sim >= threshold:
                StoryArticle.objects.create(story=best_story, article=article, similarity=best_sim)
                self._recompute_centroid(best_story)
                best_story.dirty = True
                best_story.save(update_fields=["dirty", "centroid", "last_updated"])
            else:
                candidates.append(self._new_story(user, article))
                new_stories += 1
            assigned += 1
        return assigned, new_stories

    def _recompute_centroid(self, story):
        vectors = [
            sa.article.embedding
            for sa in story.story_articles.select_related("article")
            if sa.article.embedding
        ]
        story.centroid = mean_vector(vectors)
