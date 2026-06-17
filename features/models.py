from django.conf import settings
from django.db import models


class UserEntitlements(models.Model):
    """Acceso a funciones por usuario: tier + beta + grants/denies puntuales.

    Lo gestiona el operador (admin) o, en el futuro, el flujo de pago. Ver
    features/registry.py para la lógica de resolución.
    """

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="entitlements")
    tier = models.CharField(max_length=20, default="free")
    beta_access = models.BooleanField(default=False, help_text="Acceso a funciones beta")
    grants = models.JSONField(default=list, blank=True, help_text="Keys concedidas pese al tier")
    denies = models.JSONField(default=list, blank=True, help_text="Keys denegadas explícitamente")
    tier_expires = models.DateTimeField(null=True, blank=True, help_text="Al expirar, baja a free")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user}: {self.tier}"
