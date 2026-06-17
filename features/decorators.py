"""Gating de vistas por función. Si el usuario no tiene acceso → 403."""
from __future__ import annotations

from functools import wraps

from django.http import HttpResponseForbidden

from .registry import FEATURES, has_feature


def feature_required(key):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not has_feature(request.user, key):
                label = FEATURES[key].label if key in FEATURES else key
                return HttpResponseForbidden(f"Función no disponible en tu plan: {label}")
            return view(request, *args, **kwargs)
        return wrapped
    return decorator
