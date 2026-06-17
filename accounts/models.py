import secrets

from django.conf import settings
from django.db import models


def generate_token():
    return secrets.token_urlsafe(32)


class UserConfig(models.Model):
    """Overrides de configuración por usuario (clave→valor en JSON).

    Solo se usan para los campos que el operador NO fijó en .env. Ver
    aiproviders.config para la resolución en cascada (.env > usuario > default).
    """

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="config")
    data = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Config de {self.user}"


class ApiToken(models.Model):
    """Token de API por usuario para el servidor MCP."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_tokens")
    name = models.CharField(max_length=100, default="default")
    token = models.CharField(max_length=64, unique=True, default=generate_token, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user}: {self.name}"
