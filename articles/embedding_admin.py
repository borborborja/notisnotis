"""Mantenimiento de embeddings: estado, recálculo y cambio de dimensión pgvector.

Necesario al cambiar de modelo/proveedor de embeddings: los vectores antiguos siguen
guardados y `embed_articles` solo rellena los que faltan. Aquí están las operaciones
para invalidarlos (que se regeneren) y, en Postgres, cambiar la dimensión de la columna.
"""
from __future__ import annotations

from django.db import connection

_INDEX = "article_embedding_vec_hnsw"


def sample_embedding_dim(user):
    """Dimensión de los embeddings actuales del usuario (None si no hay)."""
    from articles.models import Article

    vec = (Article.objects.filter(feed__user=user, embedding__isnull=False)
           .values_list("embedding", flat=True).first())
    return len(vec) if vec else None


def pgvector_column_dim():
    """Dimensión fijada en la columna pgvector, o None (SQLite / sin dimensión)."""
    if connection.vendor != "postgresql":
        return None
    with connection.cursor() as cur:
        cur.execute(
            "SELECT atttypmod FROM pg_attribute "
            "WHERE attrelid = 'articles_article'::regclass AND attname = 'embedding_vec'"
        )
        row = cur.fetchone()
    if not row or row[0] is None or row[0] < 0:
        return None
    return int(row[0])


def reset_user_embeddings(user):
    """Invalida los embeddings del usuario y borra sus historias (se reconstruyen)."""
    from articles.models import Article
    from stories.models import Story

    n = Article.objects.filter(feed__user=user).update(
        embedding=None, embedding_vec=None, embedded_at=None)
    Story.objects.filter(user=user).delete()
    return n


def reindex_user_articles(user):
    """Reprocesa TODO del usuario: invalida embeddings + análisis IA y borra historias.

    Tras esto, el pipeline (scheduler) re-embebe, re-agrupa y re-analiza con el proveedor
    actual; el enriquecimiento del lector se rehace al abrir cada artículo (on_demand) o en
    lote si enrich_mode=batch. Útil al cambiar de proveedor (p.ej. de mock a OpenAI).
    """
    from articles.models import Article
    from stories.models import Story

    n = Article.objects.filter(feed__user=user).update(
        embedding=None, embedding_vec=None, embedded_at=None,
        context="", claims=[], framing_note="", enriched_at=None,
        tldr="", summarized_at=None,
        translated_title="", translated_body="", translation_lang="", translated_at=None,
    )
    Story.objects.filter(user=user).delete()
    return n


def reset_all_embeddings():
    """Invalida TODOS los embeddings y borra TODAS las historias (operador)."""
    from articles.models import Article
    from stories.models import Story

    n = Article.objects.update(embedding=None, embedding_vec=None, embedded_at=None)
    Story.objects.all().delete()
    return n


def set_pgvector_dim(n):
    """Cambia la dimensión de la columna pgvector (solo Postgres). Requiere columna vacía.

    Devuelve True si se aplicó, False si no es Postgres.
    """
    n = int(n)
    if connection.vendor != "postgresql":
        return False
    with connection.cursor() as cur:
        cur.execute(f"DROP INDEX IF EXISTS {_INDEX}")
        cur.execute("UPDATE articles_article SET embedding_vec = NULL")
        cur.execute(f"ALTER TABLE articles_article ALTER COLUMN embedding_vec TYPE vector({n})")
        cur.execute(
            f"CREATE INDEX {_INDEX} ON articles_article "
            "USING hnsw (embedding_vec vector_cosine_ops)"
        )
    return True
