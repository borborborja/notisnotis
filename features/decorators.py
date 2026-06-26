"""Gating de vistas por función. Si el usuario no tiene acceso → 403."""
from __future__ import annotations

from functools import wraps

from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

from .modules import module_enabled
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


def module_required(key):
    """Gating de vistas por módulo/sector (curation/podcasts). Si off → vuelve al lector."""
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not module_enabled(request.user, key):
                messages.info(request, "Esa sección está desactivada en tu configuración.")
                return redirect("articles:list")
            return view(request, *args, **kwargs)
        return wrapped
    return decorator
