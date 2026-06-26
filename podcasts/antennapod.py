"""Importador de backups de AntennaPod (export de base de datos `.db`, SQLite).

Reconstruye en NotisNotis toda la información del backup y la expone como funciones del módulo
de podcasts: suscripciones, estado escuchado, posición de reproducción (resumen), duración,
favoritos, cola Up Next, velocidad y skip intro/outro por podcast, capítulos y carpetas.

Esquema AntennaPod (PodDBAdapter): Feeds, FeedItems, FeedMedia, Queue, Favorites, SimpleChapters.
"""
from __future__ import annotations

import sqlite3
from datetime import timezone as _tz

from django.db import transaction
from django.utils import timezone

PLAYED = 1  # FeedItems.read: NEW=-1, UNPLAYED=0, PLAYED=1


def _ms_to_dt(ms):
    try:
        ms = int(ms or 0)
    except (TypeError, ValueError):
        return None
    if ms <= 0:
        return None
    return timezone.datetime.fromtimestamp(ms / 1000, tz=_tz.utc)


def _rows(con, table):
    try:
        cur = con.execute(f"SELECT * FROM {table}")
    except sqlite3.OperationalError:
        return []
    return [dict(r) for r in cur.fetchall()]


def import_backup(user, db_path):
    """Importa el backup. Devuelve un dict con recuentos por tipo."""
    from articles.models import Article
    from feeds.models import Category, Feed, Source
    from feeds.opml import _domain

    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    counts = {"feeds": 0, "episodes": 0, "played": 0, "favorites": 0, "queue": 0, "chapters": 0}

    try:
        media_by_item = {}
        for m in _rows(con, "FeedMedia"):
            media_by_item[m.get("feeditem")] = m
        chapters_by_item = {}
        for c in _rows(con, "SimpleChapters"):
            chapters_by_item.setdefault(c.get("feeditem"), []).append(
                {"start": int((c.get("start") or 0) / 1000), "title": c.get("title") or "",
                 "link": c.get("link") or "", "image": c.get("image_url") or ""})
        fav_items = {f.get("feeditem") for f in _rows(con, "Favorites")}
        queue_items = [q.get("feeditem") for q in sorted(_rows(con, "Queue"),
                                                         key=lambda q: q.get("id") or 0)]

        ap_feed_to_local = {}
        cat_cache = {}

        with transaction.atomic():
            # --- Feeds (suscripciones) ---
            for f in _rows(con, "Feeds"):
                dl = (f.get("download_url") or "").strip()
                if not dl:
                    continue
                title = (f.get("custom_title") or f.get("title") or "").strip()[:500]
                domain = _domain(f.get("link") or dl) or _domain(dl) or "unknown"
                source, _ = Source.objects.get_or_create(domain=domain,
                                                         defaults={"name": title or domain})
                category = None
                tags = (f.get("feed_tags") or "").strip()
                if tags:
                    first = tags.split(",")[0].strip()[:200]
                    if first and first.lower() not in ("#root", "#all"):
                        if first not in cat_cache:
                            cat_cache[first], _ = Category.objects.get_or_create(user=user, name=first)
                        category = cat_cache[first]
                feed, created = Feed.objects.get_or_create(
                    user=user, url=dl,
                    defaults={"source": source, "title": title, "kind": "podcast", "category": category},
                )
                changed = []
                if feed.kind != "podcast":
                    feed.kind = "podcast"; changed.append("kind")
                if not feed.image_url and f.get("image_url"):
                    feed.image_url = (f["image_url"] or "")[:1000]; changed.append("image_url")
                if not feed.description and f.get("description"):
                    feed.description = (f["description"] or "")[:5000]; changed.append("description")
                if f.get("feed_playback_speed"):
                    try:
                        sp = float(f["feed_playback_speed"])
                        if sp and sp > 0 and feed.playback_speed != sp:
                            feed.playback_speed = sp; changed.append("playback_speed")
                    except (TypeError, ValueError):
                        pass
                for src_col, dst in (("feed_skip_intro", "skip_intro"), ("feed_skip_ending", "skip_outro")):
                    val = f.get(src_col)
                    if val and getattr(feed, dst) != int(val):
                        setattr(feed, dst, int(val)); changed.append(dst)
                if category and feed.category_id is None:
                    feed.category = category; changed.append("category")
                if changed:
                    feed.save(update_fields=changed)
                ap_feed_to_local[f.get("id")] = feed
                counts["feeds"] += 1

            # --- FeedItems + FeedMedia (episodios + estado) ---
            item_to_article = {}
            for it in _rows(con, "FeedItems"):
                feed = ap_feed_to_local.get(it.get("feed"))
                if feed is None:
                    continue
                media = media_by_item.get(it.get("id")) or {}
                guid = (it.get("item_identifier") or it.get("link")
                        or media.get("download_url") or f"ap-{it.get('id')}")[:1000]
                enc = (media.get("download_url") or "")[:1000]
                article, _ = Article.objects.get_or_create(
                    feed=feed, guid=guid,
                    defaults={
                        "source": feed.source, "url": (it.get("link") or "")[:1000],
                        "title": (it.get("title") or "(sin título)")[:500],
                        "summary": it.get("description") or "",
                        "published_at": _ms_to_dt(it.get("pubDate")),
                        "enclosure_url": enc, "enclosure_type": (media.get("mime_type") or "audio/mpeg")[:64],
                        "image_url": (it.get("image_url") or "")[:1000],
                    },
                )
                fields = []
                if media.get("duration") and not article.duration:
                    article.duration = int(media["duration"] / 1000); fields.append("duration")
                pos = int((media.get("position") or 0) / 1000)
                if pos and article.play_position != pos:
                    article.play_position = pos; fields.append("play_position")
                if it.get("read") == PLAYED and not article.is_read:
                    article.is_read = True
                    article.read_at = _ms_to_dt(media.get("last_played_time")) or timezone.now()
                    fields += ["is_read", "read_at"]
                    counts["played"] += 1
                if it.get("id") in fav_items and not article.is_saved:
                    article.is_saved = True; fields.append("is_saved")
                    counts["favorites"] += 1
                ch = chapters_by_item.get(it.get("id"))
                if ch and not article.chapters:
                    article.chapters = ch; fields.append("chapters")
                    counts["chapters"] += 1
                if fields:
                    article.play_updated_at = timezone.now(); fields.append("play_updated_at")
                    article.save(update_fields=fields)
                item_to_article[it.get("id")] = article
                counts["episodes"] += 1

            # --- Cola Up Next ---
            from .models import QueueItem
            for pos, item_id in enumerate(queue_items):
                art = item_to_article.get(item_id)
                if art is None:
                    continue
                QueueItem.objects.get_or_create(user=user, article=art, defaults={"position": pos})
                counts["queue"] += 1
    finally:
        con.close()
    return counts
