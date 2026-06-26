"""Búsqueda en un directorio de podcasts vía la iTunes Search API (gratis, sin clave).

Devuelve resultados normalizados con el feed RSS para suscribirse. Si en el futuro se quiere
otro directorio (Podcast Index), basta cambiar este módulo.
"""
from __future__ import annotations

import requests
from django.conf import settings

ITUNES_URL = "https://itunes.apple.com/search"


def search_podcasts(term, *, limit=20, timeout=15):
    """Busca podcasts por nombre. Devuelve [{title, feed_url, author, artwork}]."""
    term = (term or "").strip()
    if not term:
        return []
    resp = requests.get(
        ITUNES_URL,
        params={"media": "podcast", "entity": "podcast", "term": term, "limit": limit},
        headers={"User-Agent": settings.RSS_USER_AGENT},
        timeout=timeout,
    )
    resp.raise_for_status()
    out = []
    for r in resp.json().get("results", []):
        feed_url = r.get("feedUrl")
        if not feed_url:
            continue
        out.append({
            "title": (r.get("collectionName") or r.get("trackName") or feed_url)[:300],
            "feed_url": feed_url,
            "author": (r.get("artistName") or "")[:200],
            "artwork": r.get("artworkUrl100") or r.get("artworkUrl60") or "",
        })
    return out
