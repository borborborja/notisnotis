from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone as dt_timezone

import feedparser
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from articles.models import Article
from feeds.filters import filter_prefs, is_blocked
from feeds.models import Feed
from feeds.rules import apply_rules, load_rules

WORKERS = 16


def _parse_published(entry):
    for key in ("published_parsed", "updated_parsed"):
        val = entry.get(key)
        if val:
            return datetime(*val[:6], tzinfo=dt_timezone.utc)
    return None


def _enclosure(entry):
    for enc in entry.get("enclosures", []) or []:
        href = enc.get("href") or enc.get("url")
        if href:
            return href, enc.get("type", "")
    for link in entry.get("links", []) or []:
        if link.get("rel") == "enclosure" and link.get("href"):
            return link["href"], link.get("type", "")
    return "", ""


def _download(feed):
    """Descarga (red) un feed con conditional GET. Devuelve (feed, parsed | None, error)."""
    try:
        parsed = feedparser.parse(
            feed.url,
            agent=settings.RSS_USER_AGENT,
            etag=feed.etag or None,
            modified=feed.last_modified or None,
        )
        return feed, parsed, None
    except Exception as exc:  # noqa: BLE001
        return feed, None, str(exc)[:500]


class Command(BaseCommand):
    help = "Descarga feeds (concurrente + conditional GET); filtros, dedupe, enclosures, crawler."

    def add_arguments(self, parser):
        parser.add_argument("--user", help="limitar a un username")
        parser.add_argument("--limit", type=int, default=0, help="máx. entradas por feed (0 = todas)")
        parser.add_argument("--force", action="store_true", help="ignorar la cadencia (descargar todos)")
        parser.add_argument("--feed", type=int, help="limitar a un id de feed")
        parser.add_argument("--category", type=int, help="limitar a un id de categoría")
        parser.add_argument("--workers", type=int, default=WORKERS)

    def handle(self, *args, **opts):
        feeds = Feed.objects.filter(enabled=True).select_related("source", "user")
        if opts.get("user"):
            feeds = feeds.filter(user__username=opts["user"])
        if opts.get("feed"):
            feeds = feeds.filter(id=opts["feed"])
        if opts.get("category"):
            feeds = feeds.filter(category_id=opts["category"])

        now = timezone.now()
        due = [f for f in feeds if opts["force"] or f.is_due(now)]
        skipped = feeds.count() - len(due) if hasattr(feeds, "count") else 0

        # --- Red en paralelo; BD secuencial (seguro con SQLite) ---
        prefs_cache, rules_cache, topics_cache = {}, {}, {}
        total_new, total_blocked, not_modified, errors = 0, 0, 0, 0
        with ThreadPoolExecutor(max_workers=max(1, opts["workers"])) as pool:
            for feed, parsed, error in pool.map(_download, due):
                if error or parsed is None:
                    self._mark_error(feed, error or "desconocido")
                    errors += 1
                    continue
                status = getattr(parsed, "status", 200)
                if status == 304:
                    not_modified += 1
                    feed.last_fetched = timezone.now(); feed.fail_count = 0
                    feed.save(update_fields=["last_fetched", "fail_count"])
                    continue
                if status and status >= 400:
                    self._mark_error(feed, f"HTTP {status}")
                    errors += 1
                    continue

                prefs = prefs_cache.get(feed.user_id)
                if prefs is None:
                    prefs = prefs_cache[feed.user_id] = filter_prefs(feed.user)
                new_for_feed, new_articles = self._ingest(feed, parsed, prefs, opts["limit"])
                total_new += new_for_feed
                total_blocked += getattr(self, "_last_blocked", 0)

                rules = rules_cache.get(feed.user_id)
                if rules is None:
                    rules = rules_cache[feed.user_id] = load_rules(feed.user)
                if rules:
                    for art in new_articles:
                        apply_rules(art, rules)

                if new_articles:
                    self._notify_topics(feed.user, new_articles, topics_cache)

                if feed.crawler and settings.FULLTEXT_ENABLED:
                    self._crawl(new_articles)

                feed.etag = (getattr(parsed, "etag", "") or "")[:512]
                feed.last_modified = (getattr(parsed, "modified", "") or "")[:128]
                feed.last_fetched = timezone.now()
                feed.last_error = "" if not parsed.get("bozo") else str(parsed.get("bozo_exception", ""))[:500]
                feed.fail_count = 0
                feed.save(update_fields=["etag", "last_modified", "last_fetched", "last_error", "fail_count"])

        self.stdout.write(self.style.SUCCESS(
            f"Nuevos: {total_new} | bloqueados: {total_blocked} | 304: {not_modified} | "
            f"errores: {errors} | no vencidos: {skipped}"
        ))

    def _ingest(self, feed, parsed, prefs, limit):
        entries = parsed.entries[:limit] if limit else parsed.entries
        new_count, new_articles, blocked = 0, [], 0
        for entry in entries:
            url = entry.get("link", "")
            guid = entry.get("id", "") or url
            if not url and not guid:
                continue
            title = entry.get("title", "(sin título)")[:500]
            summary = entry.get("summary", "")
            if is_blocked(title, summary, prefs["block"], prefs["keep"]):
                blocked += 1
                continue
            if self._is_duplicate(feed, prefs["dedupe"], url, title):
                continue
            enc_url, enc_type = _enclosure(entry)
            obj, created = Article.objects.get_or_create(
                feed=feed, guid=guid,
                defaults={
                    "source": feed.source, "url": url, "title": title, "summary": summary,
                    "published_at": _parse_published(entry),
                    "enclosure_url": enc_url[:1000], "enclosure_type": enc_type[:64],
                },
            )
            if created:
                new_count += 1
                new_articles.append(obj)
        self._last_blocked = blocked
        return new_count, new_articles

    def _is_duplicate(self, feed, mode, url, title):
        if mode == "url" and url:
            return Article.objects.filter(feed__user_id=feed.user_id, url=url).exists()
        if mode == "title" and title:
            return Article.objects.filter(feed__user_id=feed.user_id, title=title).exists()
        return False

    def _notify_topics(self, user, articles, cache):
        topics = cache.get(user.id)
        if topics is None:
            from stories.topics import load_notify_topics

            topics = cache[user.id] = load_notify_topics(user)
        if not topics:
            return
        from notifications.push import send_push
        from stories.topics import article_matches

        for art in articles:
            for topic, terms in topics:
                if article_matches(terms, art):
                    try:
                        send_push(user, f"Tema: {topic.name}", art.title, url=f"/articles/{art.pk}/")
                    except Exception:  # noqa: BLE001
                        pass
                    break

    def _crawl(self, articles):
        from articles.fulltext import populate_full_text

        for art in articles:
            try:
                populate_full_text(art, enabled=True)
            except Exception:  # noqa: BLE001
                pass

    def _mark_error(self, feed, msg):
        feed.last_error = msg
        feed.fail_count = (feed.fail_count or 0) + 1
        # Backoff: tras 10 fallos seguidos, desactiva el feed.
        if feed.fail_count >= 10:
            feed.enabled = False
        feed.last_fetched = timezone.now()
        feed.save(update_fields=["last_error", "fail_count", "enabled", "last_fetched"])
        self.stderr.write(f"[error] {feed.url}: {msg}")
