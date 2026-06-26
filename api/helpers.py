"""Utilidades comunes de la API: JSON, errores, parseo, cursores y módulos."""
from __future__ import annotations

import json
import re

from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime


def _parse_dt(value):
    """Parsea ISO8601 tolerando el '+' del offset decodificado como espacio en la query."""
    if not value:
        return None
    dt = parse_datetime(value)
    if dt is None:  # "...531472 00:00" → "...531472+00:00" (el + llegó como espacio)
        dt = parse_datetime(re.sub(r" (\d{2}:\d{2})$", r"+\1", value))
    if dt is None:
        return None
    return timezone.make_aware(dt) if timezone.is_naive(dt) else dt


def ok(data, **extra):
    payload = {"data": data}
    payload.update(extra)
    return JsonResponse(payload)


def err(code, message, status=400):
    return JsonResponse({"error": {"code": code, "message": message}}, status=status)


def iso(dt):
    return dt.isoformat() if dt else None


def body_json(request):
    """Cuerpo JSON del request (dict). {} si vacío o inválido."""
    try:
        return json.loads(request.body.decode() or "{}")
    except (ValueError, UnicodeDecodeError):
        return {}


def param(request, key, default=None):
    return request.GET.get(key, default)


def as_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_since(value):
    """ISO8601 → datetime aware, o None."""
    return _parse_dt(value)


def make_cursor(dt, pk):
    """Cursor compuesto (updated_at, id) → string opaco."""
    return f"{dt.isoformat()}|{pk}" if dt else ""


def parse_cursor(value):
    """Cursor → (datetime, id) o (None, None)."""
    if not value or "|" not in value:
        return None, None
    raw_dt, _, raw_id = value.rpartition("|")
    dt = _parse_dt(raw_dt)
    try:
        pk = int(raw_id)
    except ValueError:
        pk = None
    return dt, pk


def require_module(user, key):
    """Devuelve None si el módulo está activo; si no, una respuesta 404 de error."""
    from features.modules import module_enabled

    if module_enabled(user, key):
        return None
    return err("module_disabled", f"El módulo '{key}' no está activo.", status=404)


def server_time():
    return timezone.now().isoformat()
