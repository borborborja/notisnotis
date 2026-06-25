"""Índice HNSW (coseno) sobre `embedding_vec` para búsqueda ANN en Postgres.

Se usa SeparateDatabaseAndState: el `state_operation` (AddIndex) mantiene coherente
el estado de migraciones de Django en cualquier motor, mientras que el DDL real solo
se ejecuta en Postgres (en SQLite no existe `USING hnsw`).
"""
from django.db import migrations
from pgvector.django import HnswIndex


def create_index(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        "CREATE INDEX IF NOT EXISTS article_embedding_vec_hnsw "
        "ON articles_article USING hnsw (embedding_vec vector_cosine_ops)"
    )


def drop_index(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("DROP INDEX IF EXISTS article_embedding_vec_hnsw")


class Migration(migrations.Migration):

    dependencies = [
        ("articles", "0006_article_embedding_vec"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddIndex(
                    model_name="article",
                    index=HnswIndex(
                        name="article_embedding_vec_hnsw",
                        fields=["embedding_vec"],
                        m=16,
                        ef_construction=64,
                        opclasses=["vector_cosine_ops"],
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(create_index, drop_index),
            ],
        ),
    ]
