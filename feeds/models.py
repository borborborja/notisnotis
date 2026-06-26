from django.conf import settings
from django.db import models


class Bias(models.TextChoices):
    LEFT = "left", "Izquierda"
    LEAN_LEFT = "lean_left", "Centro-izquierda"
    CENTER = "center", "Centro"
    LEAN_RIGHT = "lean_right", "Centro-derecha"
    RIGHT = "right", "Derecha"
    UNKNOWN = "unknown", "Desconocido"


# Buckets ordenados de izquierda a derecha (para barras y blindspot).
BIAS_ORDER = [Bias.LEFT, Bias.LEAN_LEFT, Bias.CENTER, Bias.LEAN_RIGHT, Bias.RIGHT]
LEFT_BUCKETS = {Bias.LEFT, Bias.LEAN_LEFT}
RIGHT_BUCKETS = {Bias.RIGHT, Bias.LEAN_RIGHT}


class Source(models.Model):
    """Publicación / medio. Global y compartida entre usuarios; el sesgo se cachea aquí."""

    name = models.CharField(max_length=255)
    domain = models.CharField(max_length=255, unique=True)
    bias = models.CharField(max_length=16, choices=Bias.choices, default=Bias.UNKNOWN)
    factuality = models.CharField(max_length=64, blank=True)
    bias_source = models.CharField(
        max_length=8,
        choices=[("llm", "LLM"), ("manual", "Manual")],
        blank=True,
    )
    bias_reasoning = models.TextField(blank=True)
    favicon = models.TextField(blank=True)  # data URI cacheado
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name or self.domain

    @property
    def needs_rating(self):
        return self.bias == Bias.UNKNOWN


class Rule(models.Model):
    """Regla de automatización: si un artículo nuevo cumple la condición, aplica acciones."""

    MATCH_CHOICES = [("any", "Título o resumen"), ("title", "Título"), ("summary", "Resumen")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="rules")
    name = models.CharField(max_length=200)
    enabled = models.BooleanField(default=True)
    position = models.IntegerField(default=0)
    # Condición (todas las indicadas se combinan con AND; vacías = comodín)
    pattern = models.CharField(max_length=300, blank=True, help_text="Regex (opcional)")
    match_in = models.CharField(max_length=8, choices=MATCH_CHOICES, default="any")
    feed = models.ForeignKey("Feed", on_delete=models.CASCADE, null=True, blank=True)
    category = models.ForeignKey("Category", on_delete=models.CASCADE, null=True, blank=True)
    # Acciones
    action_mark_read = models.BooleanField(default=False)
    action_star = models.BooleanField(default=False)
    action_tag = models.ForeignKey("articles.Tag", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return self.name


class Category(models.Model):
    """Carpeta/categoría de feeds, por usuario (estilo Feedly)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=200)
    position = models.IntegerField(default=0)

    class Meta:
        ordering = ["position", "name"]
        verbose_name_plural = "Categories"
        constraints = [
            models.UniqueConstraint(fields=["user", "name"], name="uniq_user_category_name"),
        ]

    def __str__(self):
        return self.name


class Feed(models.Model):
    """Feed RSS de un usuario (importado desde su OPML)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="feeds")
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="feeds"
    )
    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name="feeds")
    url = models.URLField(max_length=1000)
    title = models.CharField(max_length=500, blank=True)
    # Tipo de fuente: RSS normal, podcast (audio) o canal de YouTube (vídeo).
    KIND_CHOICES = [("rss", "RSS"), ("podcast", "Podcast"), ("youtube", "YouTube")]
    kind = models.CharField(max_length=16, choices=KIND_CHOICES, default="rss")
    enabled = models.BooleanField(default=True)
    last_fetched = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Conditional GET (ahorra ancho de banda) + backoff por errores.
    etag = models.CharField(max_length=512, blank=True)
    last_modified = models.CharField(max_length=128, blank=True)
    fail_count = models.PositiveIntegerField(default=0)
    # Cadencia de descarga en background (minutos). auto_interval = modo inteligente:
    # se ajusta solo según la frecuencia de publicación de la fuente.
    fetch_interval_minutes = models.PositiveIntegerField(default=60)
    auto_interval = models.BooleanField(default=True)
    # Crawler: descargar el texto completo automáticamente al recibir artículos.
    crawler = models.BooleanField(default=False)
    # Podcast: portada, descripción y ajustes de reproducción por podcast.
    image_url = models.URLField(max_length=1000, blank=True)
    description = models.TextField(blank=True)
    playback_speed = models.FloatField(default=1.0)
    skip_intro = models.PositiveIntegerField(default=0)   # segundos al empezar
    skip_outro = models.PositiveIntegerField(default=0)   # segundos al final

    def is_due(self, now):
        from datetime import timedelta

        if self.last_fetched is None:
            return True
        return now - self.last_fetched >= timedelta(minutes=self.fetch_interval_minutes)

    class Meta:
        ordering = ["title"]
        constraints = [
            models.UniqueConstraint(fields=["user", "url"], name="uniq_user_feed_url"),
        ]

    def __str__(self):
        return self.title or self.url
