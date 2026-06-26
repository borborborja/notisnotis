"""Añade `transcribe_requested` y saca el índice HNSW del ESTADO del modelo.

El índice ANN de pgvector sigue existiendo en la BD de Postgres (lo creó 0007); aquí solo se
elimina del estado de migraciones para que SQLite pueda rehacer la tabla al añadir campos sin
intentar recrear un índice con SQL incompatible. En Postgres no se toca el índice real.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("articles", "0007_article_embedding_vec_hnsw"),
    ]

    operations = [
        # Solo estado: el índice real de Postgres se conserva.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveIndex(model_name="article", name="article_embedding_vec_hnsw"),
            ],
            database_operations=[],
        ),
        migrations.AddField(
            model_name="article",
            name="transcribe_requested",
            field=models.BooleanField(default=False),
        ),
    ]
