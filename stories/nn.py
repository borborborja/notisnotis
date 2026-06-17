"""Backend de "vecinos más cercanos" (NN) sobre embeddings.

HOY: coseno en Python sobre `Article.embedding` (JSON). Funciona en SQLite y Postgres.
ESCALA (meta D4 — ver docs/PHASES.md): implementar AQUÍ la rama Postgres con pgvector
(`VectorField` + orden por `CosineDistance`/`<=>`), sin tocar las vistas que llaman a
estas funciones. Mantener la rama Python como fallback (SQLite/dev). NO acoplar nada a
que el embedding sea JSON fuera de este módulo.
"""
from __future__ import annotations

from .similarity import cosine


def _python_topk(qs, vector, k):
    scored = [(cosine(vector, a.embedding), a) for a in qs if a.embedding]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:k]


def top_k_articles(user, vector, k=10, exclude_pk=None):
    """Devuelve [(score, Article)] de los k artículos del usuario más cercanos a `vector`."""
    from articles.models import Article

    if not vector:
        return []
    qs = Article.objects.filter(feed__user=user, embedding__isnull=False).select_related("source")
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    # --- Punto de extensión pgvector ---
    # if connection.vendor == "postgresql" and <pgvector activo>:
    #     return [(1 - d, a) for a, d in qs.order_by(CosineDistance("embedding_vec", vector))[:k] ...]
    return _python_topk(qs, vector, k)
