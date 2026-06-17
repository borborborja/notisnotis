"""Recuperación de texto completo / salto de muros de pago.

CAVEAT: pensado para contenido al que el usuario tiene derecho de acceso. Respeta el
copyright y los términos de servicio de cada sitio. Desactivado por defecto
(FULLTEXT_ENABLED=0).

Estrategias en cascada:
  1. readability  — extracción del HTML directo (heurística de densidad con BeautifulSoup)
  2. bot          — reintento con user-agent de bot (algunos muros blandos lo permiten)
  3. archive      — versión archivada (archive.ph / Wayback Machine)
"""
from __future__ import annotations

import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.utils import timezone

_BLOCK_TAGS = ["script", "style", "nav", "header", "footer", "aside", "form", "noscript"]


def _extract_readable(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(_BLOCK_TAGS):
        tag.decompose()
    article = soup.find("article")
    root = article or soup.body or soup
    # Elige el contenedor con más texto entre <article> y divs grandes.
    candidates = [root] + root.find_all(["div", "section"], recursive=True)
    best, best_len = "", 0
    for node in candidates:
        paras = node.find_all("p", recursive=True)
        text = "\n\n".join(p.get_text(" ", strip=True) for p in paras if p.get_text(strip=True))
        if len(text) > best_len:
            best, best_len = text, len(text)
    return best.strip()


def _fetch(url: str, ua: str):
    resp = requests.get(
        url,
        headers={"User-Agent": ua, "Accept": "text/html,application/xhtml+xml"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.text


def fetch_full_text(url: str, *, enabled: bool):
    """Devuelve (texto, fuente) o (None, None). Lanza si la recuperación está desactivada."""
    if not enabled:
        raise RuntimeError("Recuperación de texto completo desactivada para este usuario.")
    if not url:
        return None, None

    # 1) HTML directo
    try:
        text = _extract_readable(_fetch(url, settings.RSS_USER_AGENT))
        if len(text) > 600:
            return text, "readability"
    except Exception:  # noqa: BLE001
        text = ""

    # 2) user-agent de bot
    try:
        text2 = _extract_readable(_fetch(url, settings.FULLTEXT_BOT_UA))
        if len(text2) > len(text):
            text = text2
        if len(text) > 600:
            return text, "readability"
    except Exception:  # noqa: BLE001
        pass

    # 3) archivo
    for prefix, label in (("https://archive.ph/newest/", "archive"), ("https://web.archive.org/web/2/", "archive")):
        try:
            arch = _extract_readable(_fetch(prefix + url, settings.FULLTEXT_BOT_UA))
            if len(arch) > len(text):
                return arch, label
        except Exception:  # noqa: BLE001
            continue

    return (text or None), ("readability" if text else None)


def populate_full_text(article, *, enabled: bool):
    """Recupera y guarda el texto completo en el artículo. Devuelve True si tuvo éxito."""
    text, source = fetch_full_text(article.url, enabled=enabled)
    if not text:
        return False
    article.full_text = text
    article.fulltext_source = source or ""
    article.fulltext_fetched_at = timezone.now()
    article.save(update_fields=["full_text", "fulltext_source", "fulltext_fetched_at"])
    return True
