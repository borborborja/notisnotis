from django.conf import settings
from django.db import models


class QueueItem(models.Model):
    """Episodio en la cola "Up Next" de un usuario (ordenada)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="queue_items")
    article = models.ForeignKey("articles.Article", on_delete=models.CASCADE,
                                related_name="queue_items")
    position = models.PositiveIntegerField(default=0)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "added_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "article"], name="uniq_user_queue_article"),
        ]

    def __str__(self):
        return f"{self.user} · {self.article_id} @ {self.position}"
