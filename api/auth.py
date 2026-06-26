"""Autenticación de la API por token Bearer (accounts.ApiToken)."""
from __future__ import annotations

from functools import wraps

from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .helpers import err


def user_from_bearer(request):
    """Devuelve el usuario del token Bearer (o None). Toca last_used."""
    header = request.META.get("HTTP_AUTHORIZATION", "")
    if not header.startswith("Bearer "):
        return None
    token = header[7:].strip()
    if not token:
        return None
    from accounts.models import ApiToken

    api = ApiToken.objects.select_related("user").filter(token=token).first()
    if not api or not api.user.is_active:
        return None
    ApiToken.objects.filter(pk=api.pk).update(last_used=timezone.now())
    return api.user


def api_token(view):
    """Exige Bearer válido; pone request.api_user. Exento de CSRF (API por token)."""
    @csrf_exempt
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = user_from_bearer(request)
        if user is None:
            return err("unauthorized", "Token ausente o inválido.", status=401)
        request.api_user = user
        return view(request, *args, **kwargs)

    return wrapper
