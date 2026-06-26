"""Feeds creados con IA: el usuario describe un tema, la app busca por internet,
propone noticias y aprende de las que el usuario marca como relevantes o no.

Los artículos aceptados se crean como `Article` normales en un Feed sintético, de modo que
heredan todo el pipeline existente (embeddings, enriquecimiento, clustering) y el lector.
"""
from django.conf import settings
from django.db import models

from feeds.models import Feed


class AIFeed(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_feeds")
    name = models.CharField(max_length=200)
    description = models.TextField(help_text="En lenguaje natural: qué noticias quieres")
    # Feed sintético donde aterrizan los artículos aceptados (aifeed://<id>).
    feed = models.OneToOneField(Feed, on_delete=models.SET_NULL, null=True, blank=True, related_name="ai_feed")
    enabled = models.BooleanField(default=True)
    min_score = models.PositiveSmallIntegerField(default=6)  # umbral para PROPONER (0-10)
    # Umbral para AÑADIR automáticamente al feed (sin aprobación), una vez entrenado.
    # 11 = desactivado (todo pasa por aprobación manual).
    auto_accept_score = models.PositiveSmallIntegerField(default=9)
    last_run = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class AIFeedExample(models.Model):
    """Feedback del usuario (encaja / no encaja) usado como few-shot para refinar."""

    ai_feed = models.ForeignKey(AIFeed, on_delete=models.CASCADE, related_name="examples")
    title = models.CharField(max_length=500)
    snippet = models.TextField(blank=True)
    url = models.URLField(max_length=1000, blank=True)
    relevant = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class AIFeedCandidate(models.Model):
    """Propuesta de noticia pendiente de que el usuario la valide."""

    PENDING, ACCEPTED, REJECTED = "pending", "accepted", "rejected"
    STATUS = [(PENDING, "Pendiente"), (ACCEPTED, "Aceptada"), (REJECTED, "Descartada")]

    ai_feed = models.ForeignKey(AIFeed, on_delete=models.CASCADE, related_name="candidates")
    url = models.URLField(max_length=1000)
    title = models.CharField(max_length=500)
    snippet = models.TextField(blank=True)
    score = models.PositiveSmallIntegerField(default=0)
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default=PENDING)
    article = models.ForeignKey("articles.Article", on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-score", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["ai_feed", "url"], name="uniq_aifeed_candidate_url"),
        ]

    def __str__(self):
        return self.title
