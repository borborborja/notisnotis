"""Resolución de usuario para las APIs de sincronización."""
from __future__ import annotations

import base64

from .models import SyncCredential


def user_from_basic(request, username=None):
    """gpodder: HTTP Basic (usuario + app-password de SyncCredential). Devuelve usuario o None."""
    header = request.META.get("HTTP_AUTHORIZATION", "")
    if not header.startswith("Basic "):
        return None
    try:
        raw = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8", "replace")
        user, _, pwd = raw.partition(":")
    except Exception:  # noqa: BLE001
        return None
    cred = (SyncCredential.objects.select_related("user")
            .filter(user__username=user, password=pwd).first())
    if not cred:
        return None
    if username and cred.user.get_username() != username:
        return None
    return cred.user


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
