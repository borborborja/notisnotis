"""Registro central de funciones (feature flags + tiers + beta + overrides por usuario).

OBJETIVO: poder, en el futuro, asignar tiers de pago, encender/apagar funciones por
usuario y gestionar betas, SIN tocar el código de cada función.

DISEÑO:
- Cada función se declara UNA vez aquí (`FEATURES`): key, etiqueta, tier mínimo, beta, categoría.
- Los tiers son una lista ordenada (`TIERS`); una función exige un tier mínimo por rango.
- El acceso por usuario se guarda en `features.UserEntitlements` (tier + beta + grants/denies).
- **Dormido por defecto**: si `FEATURES_ENFORCED` no está activo en `.env`, `has_feature`
  devuelve True para todo (salvo desactivación global). Así NO cambia el comportamiento
  actual; el día que quieras cobrar/segmentar, pones `FEATURES_ENFORCED=1` y ya está.

Uso en código:
    from features import has_feature, enabled_features
    if has_feature(request.user, "chat"): ...
    @feature_required("chat")  # en vistas (features/decorators.py)
    {% if 'chat' in features %}  # en plantillas (context processor)
"""
from __future__ import annotations

import os
from collections import namedtuple

Feature = namedtuple("Feature", "key label min_tier beta category")

# Tiers ordenados de menor a mayor (el rango = índice).
TIERS = ["free", "pro", "max"]

# --- Declaración de funciones (edítala para reasignar tiers/beta) ---
_F = [
    # núcleo (free)
    Feature("reader", "Lector RSS", "free", False, "core"),
    Feature("aggregator", "Agregador / historias", "free", False, "core"),
    Feature("search", "Búsqueda full-text", "free", False, "core"),
    Feature("tags", "Etiquetas", "free", False, "core"),
    Feature("import_export", "Importar/exportar y OPML", "free", False, "core"),
    Feature("bias_diet", "Dieta informativa", "free", False, "aggregator"),
    Feature("twofa", "Verificación en dos pasos (2FA)", "free", False, "account"),
    # pro
    Feature("enrich", "Enriquecimiento IA (contexto/claims)", "pro", False, "ai"),
    Feature("translate", "Traducir artículos", "pro", False, "ai"),
    Feature("summarize", "Resumir artículos", "pro", False, "ai"),
    Feature("rules", "Reglas de automatización", "pro", False, "workflow"),
    Feature("topics", "Seguir temas + alertas", "pro", False, "workflow"),
    Feature("trending", "Tendencias", "pro", False, "aggregator"),
    Feature("fulltext", "Texto completo / paywall", "pro", False, "reader"),
    Feature("digest", "Resumen por email", "pro", False, "notifications"),
    Feature("sync_api", "Sincronización (Fever/Google Reader)", "pro", False, "integrations"),
    # max
    Feature("chat", "Chat con la IA sobre la noticia", "max", True, "ai"),
    Feature("webpush", "Notificaciones push", "max", True, "notifications"),
    Feature("mcp", "Servidor MCP", "max", False, "integrations"),
    Feature("compare", "Comparar fuentes", "max", True, "aggregator"),
]
FEATURES = {f.key: f for f in _F}


def _bool(name, default=False):
    return os.environ.get(name, str(int(default))).strip().lower() in ("1", "true", "yes", "on")


def enforced():
    return _bool("FEATURES_ENFORCED", False)


def default_tier():
    t = os.environ.get("FEATURES_DEFAULT_TIER", "free").strip()
    return t if t in TIERS else "free"


def _globally_disabled(key):
    disabled = {x.strip() for x in os.environ.get("FEATURES_DISABLED", "").split(",") if x.strip()}
    return key in disabled


def _rank(tier):
    return TIERS.index(tier) if tier in TIERS else 0


def _entitlements(user):
    """Devuelve (tier, beta, grants, denies) sin escribir en BD; defaults si no hay fila."""
    ent = getattr(user, "_ent_cache", "x")
    if ent == "x":
        from .models import UserEntitlements

        ent = UserEntitlements.objects.filter(user=user).first()
        try:
            user._ent_cache = ent
        except Exception:  # noqa: BLE001
            pass
    if ent is None:
        return default_tier(), False, [], []
    tier = ent.tier if ent.tier in TIERS else default_tier()
    if ent.tier_expires:
        from django.utils import timezone

        if ent.tier_expires < timezone.now():
            tier = "free"
    return tier, ent.beta_access, ent.grants or [], ent.denies or []


def has_feature(user, key):
    f = FEATURES.get(key)
    if f is None:
        return True  # función no declarada → no se gatea
    if _globally_disabled(key):
        return False
    if user is None or not getattr(user, "is_authenticated", False):
        return _rank(f.min_tier) == 0 and not f.beta
    if getattr(user, "is_superuser", False):
        return True
    if not enforced():
        return True  # sistema dormido: todo activo
    tier, beta_access, grants, denies = _entitlements(user)
    if key in denies:
        return False
    if key in grants:
        return True
    if f.beta and not beta_access:
        return False
    return _rank(tier) >= _rank(f.min_tier)


def enabled_features(user):
    """Conjunto de keys disponibles para el usuario (para plantillas/context)."""
    return {k for k in FEATURES if has_feature(user, k)}
