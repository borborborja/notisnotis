"""Transcripción de episodios de audio/vídeo a texto.

Podcast (enclosure de audio) → se descarga y se manda al cliente de transcripción
(whisper local u OpenAI según la cascada). YouTube → subtítulos (sin descargar vídeo).
El resultado se guarda en `Article.full_text` con `fulltext_source="transcript"`, reusando
toda la infraestructura del lector/búsqueda.
"""
from __future__ import annotations

import re

import requests
from django.conf import settings
from django.utils import timezone

from aiproviders.client import get_transcribe_client
from aiproviders.config import effective_config

_YT_RE = re.compile(r"(?:v=|youtu\.be/|/embed/|/shorts/)([\w-]{11})")


def youtube_id(url):
    m = _YT_RE.search(url or "")
    return m.group(1) if m else None


def is_transcribable(article):
    return bool(youtube_id(article.url) or
                (article.enclosure_url and "audio" in (article.enclosure_type or "")))


def transcribe_episode(article):
    user = article.feed.user
    lang = effective_config(user).get("transcribe_lang", "") or ""
    vid = youtube_id(article.url)
    if vid:
        text = _youtube_captions(vid, lang)
    elif article.enclosure_url and "audio" in (article.enclosure_type or ""):
        text = _whisper_podcast(article, user, lang)
    else:
        raise ValueError("El artículo no tiene audio ni es de YouTube.")

    article.full_text = text
    article.fulltext_source = "transcript"
    article.fulltext_fetched_at = timezone.now()
    article.transcribe_requested = False
    article.save(update_fields=["full_text", "fulltext_source", "fulltext_fetched_at",
                                "transcribe_requested"])
    return article


def _whisper_podcast(article, user, lang):
    resp = requests.get(article.enclosure_url, timeout=300,
                        headers={"User-Agent": settings.RSS_USER_AGENT})
    resp.raise_for_status()
    fname = (article.enclosure_url.rsplit("/", 1)[-1] or "audio.mp3")[:80]
    return get_transcribe_client(user).transcribe(resp.content, filename=fname, lang=lang)


def _youtube_captions(video_id, lang):
    from youtube_transcript_api import YouTubeTranscriptApi

    langs = [lang, "es", "en"] if lang else ["es", "en"]
    try:
        items = YouTubeTranscriptApi.get_transcript(video_id, languages=langs)
    except Exception:  # noqa: BLE001 - prueba con cualquier idioma disponible
        items = YouTubeTranscriptApi.get_transcript(video_id)
    return " ".join(i["text"] for i in items).strip()
