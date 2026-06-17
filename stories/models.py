from django.conf import settings
from django.db import models

from articles.models import Article


class Story(models.Model):
    """Clúster de artículos sobre un mismo suceso, por usuario."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stories")
    headline = models.CharField(max_length=500, blank=True)
    centroid = models.JSONField(null=True, blank=True)  # vector medio de los miembros

    neutral_summary = models.TextField(blank=True)
    perspectives = models.JSONField(default=dict, blank=True)  # {left, center, right}
    bias_distribution = models.JSONField(default=dict, blank=True)  # {bucket: count}
    is_blindspot = models.BooleanField(default=False)
    blindspot_side = models.CharField(max_length=8, blank=True)  # left|right

    first_seen = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    analyzed_at = models.DateTimeField(null=True, blank=True)
    dirty = models.BooleanField(default=True)  # necesita re-análisis

    class Meta:
        ordering = ["-last_updated"]
        verbose_name_plural = "Stories"

    def __str__(self):
        return self.headline or f"Historia #{self.pk}"

    @property
    def article_count(self):
        return self.story_articles.count()


class StoryArticle(models.Model):
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name="story_articles")
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="stories")
    similarity = models.FloatField(default=0.0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["story", "article"], name="uniq_story_article"),
        ]
