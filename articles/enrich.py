"""Enriquecimiento LLM de artículos para el lector: contexto + banderas de controversia."""
from __future__ import annotations

from django.utils import timezone

from aiproviders.client import get_chat_client

SYSTEM = "Eres un editor que aporta contexto neutral. Devuelve únicamente JSON válido."

PROMPT = (
    "Analiza el siguiente artículo de noticias. Devuelve SOLO JSON con esta forma:\n"
    '{{"context": "2-3 frases de contexto de fondo que ayuden a entender la noticia",\n'
    '  "claims": [{{"text": "afirmación textual o parafraseada",\n'
    '              "flag": "controversial|disputed|opinion",\n'
    '              "note": "por qué se marca"}}],\n'
    '  "framing_note": "1 frase sobre el encuadre o el ángulo del artículo"}}\n'
    "Marca como 'disputed' lo que contradiga consensos verificables, 'controversial' "
    "lo polémico, y 'opinion' lo que sea juicio de valor presentado como hecho. "
    "Si no hay afirmaciones destacables, devuelve claims vacío.\n\n"
    "TÍTULO: {title}\nFUENTE: {source}\n\nTEXTO:\n{text}"
)

_VALID_FLAGS = {"controversial", "disputed", "opinion"}


def enrich_article(article, client=None):
    client = client or get_chat_client()
    text = article.best_text[:8000]
    messages = [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": PROMPT.format(title=article.title, source=article.source.name, text=text),
        },
    ]
    data = client.chat(messages, json=True)
    claims = []
    for c in data.get("claims", []) or []:
        if not isinstance(c, dict):
            continue
        flag = c.get("flag", "opinion")
        claims.append(
            {
                "text": str(c.get("text", ""))[:500],
                "flag": flag if flag in _VALID_FLAGS else "opinion",
                "note": str(c.get("note", ""))[:300],
            }
        )
    article.context = (data.get("context") or "")[:2000]
    article.claims = claims
    article.framing_note = (data.get("framing_note") or "")[:500]
    article.enriched_at = timezone.now()
    article.save(update_fields=["context", "claims", "framing_note", "enriched_at"])
    return article
