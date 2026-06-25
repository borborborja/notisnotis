"""Activa la extensión pgvector en Postgres (no-op en SQLite/dev).

Debe ejecutarse ANTES de crear la columna `vector` (migración siguiente), porque el
tipo `vector` solo existe si la extensión está instalada.
"""
from django.db import migrations


def create_extension(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("CREATE EXTENSION IF NOT EXISTS vector")


def drop_extension(apps, schema_editor):
    # No la eliminamos en reverse: otros objetos podrían depender de la extensión.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("articles", "0004_tag_article_tags_tag_uniq_user_tag"),
    ]

    operations = [
        migrations.RunPython(create_extension, drop_extension),
    ]
