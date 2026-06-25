"""Backend de "vecinos más cercanos" (NN) sobre embeddings.

HOY: coseno en Python sobre `Article.embedding` (JSON). Funciona en SQLite y Postgres.
ESCALA (meta D4 — ver docs/PHASES.md): implementar AQUÍ la rama Postgres con pgvector
(`VectorField` + orden por `CosineDistance`/`<=>`), sin tocar las vistas que llaman a
estas funciones. Mantener la rama Python como fallback (SQLite/dev). NO acoplar nada a
que el embedding sea JSON fuera de este módulo.
"""
from __future__ import annotations

from django.db import connection

from .similarity import cosine


def _python_topk(qs, vector, k):
    scored = [(cosine(vector, a.embedding), a) for a in qs if a.embedding]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:k]


def _pgvector_topk(qs, vector, k):
    """Top-k vía índice ANN de pgvector. Devuelve None si no está disponible."""
    try:
        from pgvector.django import CosineDistance

        rows = list(
            qs.exclude(embedding_vec__isnull=True)
            .annotate(_distance=CosineDistance("embedding_vec", vector))
            .order_by("_distance")[:k]
        )
    except Exception:  # noqa: BLE001 — extensión/columna no disponibles → fallback
        return None
    # CosineDistance = 1 - similitud_coseno; reconstruimos el score que esperan las vistas.
    return [(1 - a._distance, a) for a in rows]


def top_k_articles(user, vector, k=10, exclude_pk=None):
    """Devuelve [(score, Article)] de los k artículos del usuario más cercanos a `vector`."""
    from articles.models import Article

    if not vector:
        return []
    qs = Article.objects.filter(feed__user=user, embedding__isnull=False).select_related("source")
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    # Postgres: búsqueda ANN con pgvector. SQLite/dev o fallo: coseno en Python.
    if connection.vendor == "postgresql":
        result = _pgvector_topk(qs, vector, k)
        if result is not None:
            return result
    return _python_topk(qs, vector, k)
