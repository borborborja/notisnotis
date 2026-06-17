"""Export/import de datos de usuario + import desde Pocket/Instapaper."""
from __future__ import annotations

import csv
import io
import re

from bs4 import BeautifulSoup

from articles.models import Article, Tag
from feeds.models import Category, Feed, Source


# --------------------------------------------------------------------------- export
def export_user_data(user):
    feeds = Feed.objects.filter(user=user).select_related("source", "category")
    return {
        "version": 1,
        "categories": [c.name for c in Category.objects.filter(user=user)],
        "tags": [t.name for t in Tag.objects.filter(user=user)],
        "feeds": [
            {"url": f.url, "title": f.title, "category": f.category.name if f.category else None,
             "enabled": f.enabled, "crawler": f.crawler}
            for f in feeds
        ],
        "rules": [
            {"name": r.name, "pattern": r.pattern, "match_in": r.match_in,
             "mark_read": r.action_mark_read, "star": r.action_star,
             "tag": r.action_tag.name if r.action_tag else None}
            for r in user.rules.select_related("action_tag")
        ],
        "topics": [{"name": t.name, "keywords": t.keywords, "notify": t.notify} for t in user.topics.all()],
        "config": dict(getattr(getattr(user, "config", None), "data", {}) or {}),
        "saved_urls": list(Article.objects.filter(feed__user=user, is_saved=True).values_list("url", flat=True)),
    }


# --------------------------------------------------------------------------- import (JSON)
def import_user_data(user, data):
    from feeds.views import _create_feed

    cats = {name: Category.objects.get_or_create(user=user, name=name)[0] for name in data.get("categories", [])}
    for name in data.get("tags", []):
        Tag.objects.get_or_create(user=user, name=name)
    n_feeds = 0
    for f in data.get("feeds", []):
        feed, created = _create_feed(user, f["url"], f.get("title", ""), cats.get(f.get("category")))
        if created:
            feed.enabled = f.get("enabled", True)
            feed.crawler = f.get("crawler", False)
            feed.save(update_fields=["enabled", "crawler"])
            n_feeds += 1
    from feeds.models import Rule

    for r in data.get("rules", []):
        tag = Tag.objects.get_or_create(user=user, name=r["tag"])[0] if r.get("tag") else None
        Rule.objects.create(user=user, name=r["name"], pattern=r.get("pattern", ""),
                            match_in=r.get("match_in", "any"), action_mark_read=r.get("mark_read", False),
                            action_star=r.get("star", False), action_tag=tag)
    from stories.models import Topic

    for t in data.get("topics", []):
        Topic.objects.get_or_create(user=user, name=t["name"],
                                    defaults={"keywords": t.get("keywords", ""), "notify": t.get("notify", False)})
    if data.get("config"):
        from accounts.models import UserConfig

        cfg, _ = UserConfig.objects.get_or_create(user=user)
        cfg.data.update(data["config"])
        cfg.save(update_fields=["data"])
    return {"feeds": n_feeds}


# --------------------------------------------------------------------------- import read-it-later
def _imported_feed(user):
    src, _ = Source.objects.get_or_create(domain="imported.local", defaults={"name": "Importados"})
    feed, _ = Feed.objects.get_or_create(user=user, url="imported://saved",
                                         defaults={"source": src, "title": "Importados", "enabled": False})
    return feed


def _add_saved(user, url, title):
    if not url:
        return False
    feed = _imported_feed(user)
    _, created = Article.objects.get_or_create(
        feed=feed, guid=url, defaults={"source": feed.source, "url": url, "title": (title or url)[:500], "is_saved": True})
    return created


def import_pocket(user, html):
    soup = BeautifulSoup(html, "html.parser")
    n = sum(_add_saved(user, a.get("href"), a.get_text(strip=True)) for a in soup.find_all("a"))
    return {"saved": n}


def import_instapaper(user, text):
    reader = csv.DictReader(io.StringIO(text))
    n = 0
    for row in reader:
        url = row.get("URL") or row.get("url")
        if url:
            n += _add_saved(user, url, row.get("Title") or row.get("title"))
    return {"saved": n}


def detect_and_import(user, filename, content_bytes):
    name = (filename or "").lower()
    if name.endswith(".json"):
        import json
        return "json", import_user_data(user, json.loads(content_bytes.decode("utf-8")))
    text = content_bytes.decode("utf-8", errors="replace")
    if name.endswith(".csv") or text[:3].upper().startswith("URL"):
        return "instapaper", import_instapaper(user, text)
    return "pocket", import_pocket(user, text)
