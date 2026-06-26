"""Búsqueda web para los feeds con IA, vía SearXNG (salida JSON).

Self-hosted y configurable por `SEARCH_URL`. Devuelve resultados normalizados
[{url, title, snippet}]. Sin claves ni dependencias nuevas (usa `requests`).
"""
from __future__ import annotations

import requests
from django.conf import settings


def web_search(query, *, category="news", lang=None, k=15, timeout=20):
    """Busca en la web y devuelve una lista de {url, title, snippet}."""
    base = settings.SEARCH_URL.rstrip("/")
    params = {
        "q": query,
        "format": "json",
        "categories": category,
        "language": lang or settings.SEARCH_LANG,
        "safesearch": 0,
    }
    resp = requests.get(
        f"{base}/search", params=params, timeout=timeout,
        headers={"User-Agent": settings.RSS_USER_AGENT},
    )
    resp.raise_for_status()
    out = []
    for r in resp.json().get("results", [])[:k]:
        url = r.get("url", "")
        if not url:
            continue
        out.append({
            "url": url,
            "title": (r.get("title") or url)[:500],
            "snippet": (r.get("content") or "")[:1000],
        })
    return out
