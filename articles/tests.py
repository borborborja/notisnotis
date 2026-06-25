from django.contrib.auth import get_user_model
from django.test import TestCase

from articles.models import Article
from feeds.models import Feed, Source

H = {"HTTP_HOST": "localhost"}


class SearchTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_user("u", "", "pw")
        self.client.login(username="u", password="pw")
        self.src = Source.objects.create(name="BBC", domain="bbc.com")
        self.feed = Feed.objects.create(user_id=1, source=self.src, url="http://bbc/rss")
        Article.objects.create(feed=self.feed, source=self.src, guid="1", title="Clima y energía", body="cuerpo sobre clima", is_read=False)
        Article.objects.create(feed=self.feed, source=self.src, guid="2", title="Deportes", body="futbol", is_read=True, is_saved=True)
        Article.objects.create(feed=self.feed, source=self.src, guid="3", title="Economía", summary="mercados", is_read=False)

    def _titles(self, q):
        r = self.client.get(f"/articles/?q={q}", **H)
        return [a.title for a in r.context["page"]]

    def test_text_search_in_body(self):
        self.assertEqual(self._titles("clima"), ["Clima y energía"])

    def test_is_unread_operator(self):
        titles = self._titles("is:unread")
        self.assertIn("Clima y energía", titles)
        self.assertNotIn("Deportes", titles)

    def test_is_saved_operator(self):
        self.assertEqual(self._titles("is:saved"), ["Deportes"])


class TagTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_user("t", "", "pw")
        self.client.login(username="t", password="pw")
        self.src = Source.objects.create(name="BBC", domain="bbc.com")
        self.feed = Feed.objects.create(user_id=1, source=self.src, url="http://bbc/rss")
        self.art = Article.objects.create(feed=self.feed, source=self.src, guid="1", title="Hola", body="x")

    def test_tag_add_remove_and_filter(self):
        from articles.models import Tag

        self.client.post(f"/articles/{self.art.pk}/tag/", {"name": "fav"}, **H)
        tag = Tag.objects.get(user_id=1, name="fav")
        self.assertIn(tag, self.art.tags.all())
        r = self.client.get(f"/articles/?tag={tag.id}", **H)
        self.assertIn(self.art, list(r.context["page"]))
        self.client.post(f"/articles/{self.art.pk}/untag/", {"tag_id": tag.id}, **H)
        self.assertEqual(self.art.tags.count(), 0)

    def test_export_markdown(self):
        r = self.client.get(f"/articles/{self.art.pk}/export.md", **H)
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/markdown", r["Content-Type"])
        self.assertIn(b"# Hola", r.content)


class EmbeddingAdminTests(TestCase):
    def setUp(self):
        from stories.models import Story

        self.user = get_user_model().objects.create_user("emb", "", "pw")
        src = Source.objects.create(name="S", domain="s.com")
        feed = Feed.objects.create(user=self.user, source=src, url="http://s/rss")
        Article.objects.create(feed=feed, source=src, guid="a", title="A",
                               embedding=[0.1, 0.2, 0.3])
        Article.objects.create(feed=feed, source=src, guid="b", title="B", embedding=None)
        Story.objects.create(user=self.user, headline="H")

    def test_sample_dim(self):
        from articles.embedding_admin import sample_embedding_dim

        self.assertEqual(sample_embedding_dim(self.user), 3)

    def test_reset_user_embeddings(self):
        from articles.embedding_admin import reset_user_embeddings
        from stories.models import Story

        reset_user_embeddings(self.user)
        self.assertEqual(Article.objects.filter(feed__user=self.user, embedding__isnull=False).count(), 0)
        self.assertEqual(Story.objects.filter(user=self.user).count(), 0)

    def test_pgvector_helpers_noop_on_sqlite(self):
        from articles.embedding_admin import pgvector_column_dim, set_pgvector_dim

        # En SQLite no hay columna pgvector real: helpers degradan limpiamente.
        self.assertIsNone(pgvector_column_dim())
        self.assertFalse(set_pgvector_dim(384))


class ReembedViewTests(TestCase):
    def setUp(self):
        self.U = get_user_model()
        self.U.objects.create_user("re", "", "pw-initial-1")
        self.client.login(username="re", password="pw-initial-1")
        src = Source.objects.create(name="S", domain="s.com")
        feed = Feed.objects.create(user=self.U.objects.get(username="re"), source=src, url="http://s/rss")
        Article.objects.create(feed=feed, source=src, guid="a", title="A", embedding=[1.0, 2.0])

    def test_reembed_nulls_user_embeddings(self):
        r = self.client.post("/accounts/settings/ai/", {"action": "reembed"}, **H)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Article.objects.filter(embedding__isnull=False).count(), 0)

    def test_set_embed_dim_requires_superuser(self):
        r = self.client.post("/accounts/settings/ai/",
                             {"action": "set_embed_dim", "embed_dim_new": "384"}, **H)
        self.assertEqual(r.status_code, 302)
        # Usuario normal: NO se aplica (sus embeddings siguen).
        self.assertEqual(Article.objects.filter(embedding__isnull=False).count(), 1)

    def test_reindex_clears_embeddings_and_enrichment(self):
        from stories.models import Story

        u = self.U.objects.get(username="re")
        Article.objects.filter(feed__user=u).update(
            context="[mock] ctx", enriched_at="2026-01-01T00:00:00Z", tldr="[mock]")
        Story.objects.create(user=u, headline="H")
        r = self.client.post("/accounts/settings/ai/", {"action": "reindex"}, **H)
        self.assertEqual(r.status_code, 302)
        a = Article.objects.get(feed__user=u)
        self.assertIsNone(a.embedding)
        self.assertIsNone(a.enriched_at)
        self.assertEqual(a.context, "")
        self.assertEqual(Story.objects.filter(user=u).count(), 0)

    def test_set_embed_dim_superuser_saves(self):
        u = self.U.objects.get(username="re")
        u.is_superuser = True
        u.is_staff = True
        u.save()
        r = self.client.post("/accounts/settings/ai/",
                             {"action": "set_embed_dim", "embed_dim_new": "384"}, **H)
        self.assertEqual(r.status_code, 302)
        from accounts.models import UserConfig
        self.assertEqual(UserConfig.objects.get(user=u).data.get("embed_dim"), "384")
