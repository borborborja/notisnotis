import hashlib
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

REFRESH_MIN = 180   # no re-buscar un país más de una vez cada 3 h (salvo --force)
KEEP_DAYS = 4       # las tendencias más antiguas se podan


class Command(BaseCommand):
    help = "Tendencias globales: titulares de Google News + cobertura de SearXNG (por país)."

    def add_arguments(self, parser):
        parser.add_argument("--country", help="código de país concreto (p.ej. ES)")
        parser.add_argument("--headlines", type=int, default=15, help="titulares por país")
        parser.add_argument("--force", action="store_true", help="ignorar la cadencia")

    def handle(self, *args, **opts):
        from aifeeds.search import web_search
        from articles.models import Article
        from feeds.models import Source
        from feeds.opml import _domain
        from stories.trending import (active_countries, country_meta, top_headlines,
                                      trending_feed, trending_user)

        countries = [opts["country"].upper()] if opts.get("country") else active_countries()
        now = timezone.now()
        total = 0
        for cc in countries:
            feed = trending_feed(cc)
            if not opts["force"] and feed.last_fetched and feed.last_fetched > now - timedelta(minutes=REFRESH_MIN):
                continue
            _, _, _, _, lang = country_meta(cc)
            existing = set(feed.articles.exclude(url="").values_list("url", flat=True))
            created = 0
            for title in top_headlines(cc, limit=opts["headlines"]):
                try:
                    results = web_search(title, category="news", lang=lang, k=8)
                except Exception as exc:  # noqa: BLE001 - un titular fallido no aborta
                    self.stderr.write(f"[{cc}] {exc}")
                    continue
                for r in results:
                    url = r.get("url")
                    if not url or url in existing:
                        continue
                    existing.add(url)
                    domain = _domain(url) or "unknown"
                    source, _ = Source.objects.get_or_create(domain=domain, defaults={"name": domain})
                    guid = "trend-" + hashlib.sha1(url.encode()).hexdigest()[:24]
                    _, made = Article.objects.get_or_create(
                        feed=feed, guid=guid,
                        defaults={"source": source, "url": url[:1000], "title": r["title"][:500],
                                  "summary": r.get("snippet", ""), "published_at": now},
                    )
                    created += int(made)
            feed.last_fetched = now
            feed.save(update_fields=["last_fetched"])
            total += created
            self.stdout.write(f"{cc}: {created} artículos de tendencia")

        self._prune()
        self.stdout.write(self.style.SUCCESS(f"Tendencias: {total} artículos nuevos"))

    def _prune(self):
        """Borra artículos de tendencia antiguos y limpia historias vacías."""
        from articles.models import Article
        from stories.models import Story
        from stories.trending import trending_user, COUNTRIES

        cutoff = timezone.now() - timedelta(days=KEEP_DAYS)
        users = [trending_user(c[0]) for c in COUNTRIES]
        old = Article.objects.filter(feed__user__in=users, fetched_at__lt=cutoff)
        n = old.count()
        old.delete()  # cascada borra StoryArticle
        Story.objects.filter(user__in=users, story_articles__isnull=True).delete()
        if n:
            self.stdout.write(f"podados {n} artículos antiguos")
