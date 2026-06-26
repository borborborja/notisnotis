"""Módulos/sectores de la app (capa gruesa de activación, encima de features/tiers).

Un módulo enciende/apaga un sector ENTERO por cascada (operador en .env > usuario en Ajustes
> default). `rss` (lector básico + IA por artículo) está siempre activo. `curation` (agregador:
historias/sesgo/blindspots/perspectivas/síntesis + feeds con IA + contexto/afirmaciones por
artículo) y `podcasts` (feeds de audio/YouTube + transcripciones) se pueden desactivar.

Perfiles típicos (vía .env del operador o Ajustes del usuario):
  - curation=0 podcasts=0 → lector RSS sencillo con resúmenes IA.
  - curation=0 podcasts=1 → lector RSS + gestor de podcasts con transcripciones.
  - curation=1 podcasts=1 → todo (por defecto).

Distinto de las *features* (`features/registry.py`, acceso por tier, dormido por defecto) y de
las *capabilities* (`optconfig`, configuración). Aquí: SECTOR on/off (operador + usuario).
"""
from __future__ import annotations

from notisnotis import optconfig

# (key, env_var, default, type, secret, label, choices) — patrón optconfig.
MODULE_FIELDS = [
    ("module_curation", "MODULE_CURATION", "1", "bool", False, "Curación IA", None),
    ("module_podcasts", "MODULE_PODCASTS", "1", "bool", False, "Podcasts", None),
]
_BY_KEY = {f[optconfig.KEY]: f for f in MODULE_FIELDS}
# módulo lógico -> field key
_MODULES = {"curation": "module_curation", "podcasts": "module_podcasts"}


def enabled_modules(user=None) -> set:
    """Conjunto de módulos activos para el usuario (rss siempre)."""
    vals = optconfig.resolve(MODULE_FIELDS, user)
    mods = {"rss"}
    for mod, key in _MODULES.items():
        if vals.get(key):
            mods.add(mod)
    return mods


def module_enabled(user, key) -> bool:
    """¿Está activo el módulo `key` para el usuario? (rss siempre True)."""
    if key == "rss":
        return True
    return key in enabled_modules(user)


def modules_state(user=None):
    """Estado por módulo para la UI de Ajustes: key/label/locked/enabled."""
    vals = optconfig.resolve(MODULE_FIELDS, user)
    out = []
    for mod, fkey in _MODULES.items():
        field = _BY_KEY[fkey]
        out.append({
            "module": mod,
            "field": fkey,
            "label": field[optconfig.LABEL],
            "locked": optconfig.is_locked(field),
            "enabled": bool(vals.get(fkey)),
        })
    return out
