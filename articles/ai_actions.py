"""Acciones de IA sobre artículos: traducir, resumir, contexto y chat."""
from __future__ import annotations

from django.utils import timezone

from aiproviders.client import get_chat_client

LANGS = [
    ("es", "Español"), ("en", "Inglés"), ("ca", "Catalán"),
    ("fr", "Francés"), ("de", "Alemán"), ("pt", "Portugués"), ("it", "Italiano"),
]
LANG_NAMES = dict(LANGS)


def reading_prefs(user):
    cfg = getattr(user, "config", None)
    data = cfg.data if cfg else {}
    return {
        "lang": data.get("translate_lang", "es"),
        "auto_translate": data.get("auto_translate") == "1",
        "auto_summarize": data.get("auto_summarize") == "1",
        "auto_mark_scroll": data.get("auto_mark_scroll") == "1",
        "font": data.get("read_font", "sans"),
        "size": data.get("read_size", "m"),
        "width": data.get("read_width", "normal"),
    }


# --------------------------------------------------------------------------- traducir
def translate_article(article, lang, client=None):
    client = client or get_chat_client()
    lang_name = LANG_NAMES.get(lang, lang)
    text = article.best_text[:8000]
    user_msg = (
        f"Traduce este artículo al {lang_name}. Devuelve SOLO JSON con esta forma: "
        '{"title": "...", "body": "..."}.\n\n'
        f"TÍTULO: {article.title}\n\nTEXTO:\n{text}"
    )
    messages = [
        {"role": "system", "content": f"Eres un traductor profesional. Traduce al {lang_name}. Devuelve solo JSON."},
        {"role": "user", "content": user_msg},
    ]
    data = client.chat(messages, json=True)
    article.translated_title = (data.get("title") or "")[:500]
    article.translated_body = data.get("body") or ""
    article.translation_lang = lang
    article.translated_at = timezone.now()
    article.save(update_fields=["translated_title", "translated_body", "translation_lang", "translated_at"])
    return article


# --------------------------------------------------------------------------- resumir
def summarize_article(article, client=None):
    client = client or get_chat_client()
    text = article.best_text[:8000]
    messages = [
        {"role": "system", "content": "Resumes noticias de forma objetiva y concisa."},
        {"role": "user", "content": f"Resume en 3-4 frases clave (bullet points) esta noticia.\n\nTÍTULO: {article.title}\n\nTEXTO:\n{text}"},
    ]
    article.tldr = client.chat(messages)
    article.summarized_at = timezone.now()
    article.save(update_fields=["tldr", "summarized_at"])
    return article


# --------------------------------------------------------------------------- contexto + chat
def related_articles(article, user, k=12):
    """Artículos del usuario realmente relacionados por similitud semántica.

    Aplica un umbral mínimo de similitud y una ventana temporal: si no hay nada
    suficientemente parecido (o el artículo no tiene embedding) devuelve []. Cada artículo
    devuelto lleva `rel_score` (0-100) para mostrarlo en la UI.
    """
    from datetime import timedelta

    from django.conf import settings

    from stories.nn import top_k_articles

    if not article.embedding:
        return []
    since = timezone.now() - timedelta(days=settings.AI["RELATED_DAYS"])
    out = []
    for score, a in top_k_articles(user, article.embedding, k=k, exclude_pk=article.pk,
                                   min_score=settings.AI["RELATED_THRESHOLD"], since=since):
        a.rel_score = round(score * 100)
        out.append(a)
    return out


def build_context(article, user, k=8):
    """Mensaje de sistema con el artículo principal + cobertura relacionada."""
    prefs = reading_prefs(user)
    parts = [
        "Eres un asistente experto en esta noticia y su cobertura mediática. "
        "Responde a las preguntas del usuario basándote en el CONTEXTO de abajo "
        "(el artículo principal y artículos relacionados de varias fuentes). "
        f"Responde en {LANG_NAMES.get(prefs['lang'], 'el idioma del usuario')}. "
        "Si algo no está en el contexto, dilo con claridad.\n",
        "=== ARTÍCULO PRINCIPAL ===",
        f"Fuente: {article.source.name} ({article.source.get_bias_display()})",
        f"Título: {article.title}",
        article.best_text[:3500],
    ]
    story = article.stories.filter(story__user=user).select_related("story").first()
    if story and story.story.neutral_summary:
        parts.append("\n=== RESUMEN AGREGADO DE LA HISTORIA ===")
        parts.append(story.story.neutral_summary)

    related = related_articles(article, user, k=k)
    if related:
        parts.append("\n=== ARTÍCULOS RELACIONADOS (otras fuentes) ===")
        for r in related:
            snippet = (r.summary or r.body or "")[:240].replace("\n", " ")
            parts.append(f"- [{r.source.name} · {r.source.get_bias_display()}] {r.title}: {snippet}")
    return "\n".join(parts)


def chat_reply(article, user, history):
    """history = [{role, content}, ...] (incluye el último turno del usuario)."""
    client = get_chat_client(user)
    messages = [{"role": "system", "content": build_context(article, user)}]
    messages += history[-12:]  # acota el contexto de conversación
    return client.chat(messages)
