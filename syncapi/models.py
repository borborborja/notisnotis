import hashlib
import secrets

from django.conf import settings
from django.db import models


class SyncCredential(models.Model):
    """Credencial para lectores externos (Fever + Google Reader).

    `password` es una app-password generada (no la contraseña de la cuenta web).
    Fever usa `api_key = md5(username:password)` → cacheado en `fever_hash`.
    Google Reader autentica por `token` (header GoogleLogin auth=).
    """

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sync_credential")
    password = models.CharField(max_length=64)
    token = models.CharField(max_length=64, unique=True, db_index=True)
    fever_hash = models.CharField(max_length=32, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Sync de {self.user}"

    def regenerate(self):
        self.password = secrets.token_urlsafe(12)
        self.token = secrets.token_urlsafe(32)
        self.fever_hash = self.compute_fever_hash(self.user.get_username(), self.password)
        self.save()
        return self

    @staticmethod
    def compute_fever_hash(username, password):
        return hashlib.md5(f"{username}:{password}".encode()).hexdigest()

    @classmethod
    def get_or_create_for(cls, user):
        cred = cls.objects.filter(user=user).first()
        if cred:
            return cred
        cred = cls(user=user)
        cred.regenerate()
        return cred
