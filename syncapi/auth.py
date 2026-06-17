"""Resolución de usuario para las APIs de sincronización."""
from __future__ import annotations

from .models import SyncCredential


def user_from_fever(api_key):
    """Fever: api_key = md5(username:password). Devuelve el usuario o None."""
    if not api_key:
        return None
    cred = SyncCredential.objects.select_related("user").filter(fever_hash=api_key.strip()).first()
    return cred.user if cred else None


def user_from_greader(request):
    """Google Reader: header 'Authorization: GoogleLogin auth=<token>'."""
    header = request.META.get("HTTP_AUTHORIZATION", "")
    token = ""
    if header.startswith("GoogleLogin"):
        for part in header.split():
            if part.startswith("auth="):
                token = part[5:].strip()
    token = token or request.GET.get("T") or request.POST.get("T", "")
    if not token:
        return None
    cred = SyncCredential.objects.select_related("user").filter(token=token).first()
    return cred.user if cred else None
