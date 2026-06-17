"""Temas seguidos: matching por palabras clave (búsqueda guardada + alertas)."""
from __future__ import annotations

import re


def topic_terms(topic):
    return [t.strip().lower() for t in re.split(r"[,\n]", topic.keywords) if t.strip()]


def article_matches(terms, article):
    hay = f"{article.title}\n{article.summary}".lower()
    return any(t in hay for t in terms)


def load_notify_topics(user):
    """Temas con alerta activada, precompilados: [(topic, terms)]."""
    return [(t, topic_terms(t)) for t in user.topics.filter(notify=True) if t.keywords.strip()]
