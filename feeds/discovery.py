"""Autodescubrimiento de feeds a partir de una URL (feed directo o página HTML)."""
from __future__ import annotations

from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup
from django.conf import settings


def _looks_like_feed(text, ctype):
    head = text.lstrip()[:600].lower()
    return (
        any(x in ctype.lower() for x in ("rss", "atom", "xml"))
        or head.startswith("<?xml")
        or "<rss" in head
        or "<feed" in head
    )


def discover_feeds(url):
    """Devuelve [(feed_url, title)] candidatos. Si la URL ya es un feed, lo devuelve."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    headers = {"User-Agent": settings.RSS_USER_AGENT}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
    except Exception:  # noqa: BLE001
        return []
    text = resp.text
    ctype = resp.headers.get("Content-Type", "")

    if _looks_like_feed(text, ctype):
        parsed = feedparser.parse(text)
        if parsed.entries or parsed.feed.get("title"):
            return [(resp.url, parsed.feed.get("title", resp.url))]

    soup = BeautifulSoup(text, "html.parser")
    out, seen = [], set()
    for link in soup.find_all("link", rel=lambda v: v and "alternate" in " ".join(v).lower() if isinstance(v, list) else (v and "alternate" in v.lower())):
        t = (link.get("type") or "").lower()
        href = link.get("href")
        if href and any(x in t for x in ("rss", "atom", "xml")):
            full = urljoin(resp.url, href)
            if full not in seen:
                seen.add(full)
                out.append((full, link.get("title", "") or full))
    return out


def feed_title(feed_url):
    try:
        parsed = feedparser.parse(feed_url, agent=settings.RSS_USER_AGENT)
        return parsed.feed.get("title", "")
    except Exception:  # noqa: BLE001
        return ""
