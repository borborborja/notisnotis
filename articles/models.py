from django.conf import settings
from django.db import models
from pgvector.django import HnswIndex, VectorField

from feeds.models import Feed, Source


class Tag(models.Model):
    """Etiqueta de usuario (multi-etiqueta por artículo), más allá de is_saved."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tags")
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["user", "name"], name="uniq_user_tag")]

    def __str__(self):
        return self.name


class Article(models.Model):
    """Artículo de un feed (por usuario vía Feed)."""

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE, related_name="articles")
    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name="articles")
    guid = models.CharField(max_length=1000)
    url = models.URLField(max_length=1000, blank=True)
    title = models.CharField(max_length=500)
    summary = models.TextField(blank=True)
    body = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    fetched_at = models.DateTimeField(auto_now_add=True)
    # Adjunto multimedia (podcast/imagen/vídeo) del feed
    enclosure_url = models.URLField(max_length=1000, blank=True)
    enclosure_type = models.CharField(max_length=64, blank=True)

    # Embedding (JSON portable; similitud coseno en Python — ver stories/similarity.py)
    embedding = models.JSONField(null=True, blank=True)
    embedded_at = models.DateTimeField(null=True, blank=True)
    # Mismo embedding como vector nativo pgvector para búsqueda ANN en Postgres.
    # En SQLite/dev queda NULL y se usa el fallback coseno sobre `embedding` (JSON).
    # La dimensión debe coincidir con AI_EMBED_DIM (por defecto 256); si cambias ese
    # valor, regenera esta migración con la nueva dimensión.
    embedding_vec = VectorField(dimensions=256, null=True, blank=True)

    # Enriquecimiento LLM (lector)
    context = models.TextField(blank=True)
    claims = models.JSONField(default=list, blank=True)  # [{text, flag, note}]
    framing_note = models.TextField(blank=True)
    enriched_at = models.DateTimeField(null=True, blank=True)

    # Texto completo / muros de pago
    full_text = models.TextField(blank=True)
    fulltext_source = models.CharField(max_length=16, blank=True)  # rss|readability|archive|cache
    fulltext_fetched_at = models.DateTimeField(null=True, blank=True)

    # Traducción (LLM)
    translated_title = models.CharField(max_length=500, blank=True)
    translated_body = models.TextField(blank=True)
    translation_lang = models.CharField(max_length=8, blank=True)
    translated_at = models.DateTimeField(null=True, blank=True)

    # Resumen TL;DR (LLM)
    tldr = models.TextField(blank=True)
    summarized_at = models.DateTimeField(null=True, blank=True)

    # Estado de lectura (Feed ya es por-usuario)
    is_read = models.BooleanField(default=False)
    is_saved = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name="articles")

    class Meta:
        ordering = ["-published_at", "-fetched_at"]
        constraints = [
            models.UniqueConstraint(fields=["feed", "guid"], name="uniq_feed_guid"),
        ]
        indexes = [
            models.Index(fields=["is_read"]),
            models.Index(fields=["is_saved"]),
            # Índice ANN de pgvector (solo se materializa en Postgres; ver
            # articles/migrations/0007 — el DDL va guardado por vendor).
            HnswIndex(
                name="article_embedding_vec_hnsw",
                fields=["embedding_vec"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]

    def __str__(self):
        return self.title

    @property
    def best_text(self):
        """Mejor texto disponible para análisis/enriquecimiento."""
        return self.full_text or self.body or self.summary or self.title

    @property
    def is_enriched(self):
        return self.enriched_at is not None

    @property
    def reading_minutes(self):
        """Tiempo de lectura estimado (~200 palabras/min). 0 si no hay cuerpo."""
        text = self.full_text or self.body or self.summary or ""
        words = len(text.split())
        return max(1, round(words / 200)) if words > 30 else 0
