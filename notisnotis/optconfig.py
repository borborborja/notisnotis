"""Configuración en cascada y por capacidad (patrón ÚNICO para toda la app).

REGLA GENERAL — vale para API keys, SMTP y cualquier opción futura:

  Cada opción es un Field: (key, env_var, default, type, secret, label, choices).
  Resolución de su valor, en orden:
    1) si el operador fija `env_var` en .env con valor no vacío → BLOQUEADO: global,
       todos los usuarios lo heredan y NO pueden cambiarlo (se muestra solo lectura);
    2) si no, el valor que el usuario haya guardado en Ajustes (solo para él);
    3) si no, el `default`.

  Una "capacidad" (Capability) agrupa campos de conexión y añade:
    - `flag_env`: booleano en .env que ACTIVA/DESACTIVA la función (p.ej. DIGEST_ENABLED);
    - `required`: campos mínimos para considerarla "configurada".
  Estados resultantes:
    * flag off                          → desactivada por el operador (no se ofrece).
    * flag on + requeridos en .env      → GLOBAL: el usuario solo ve sus preferencias,
                                          no la conexión (la pone el operador).
    * flag on + requeridos NO en .env   → el usuario rellena la conexión en sus Ajustes.

Almacenamiento por usuario: `accounts.UserConfig.data` (un dict JSON con la `key`).
"""
from __future__ import annotations

import os

# Índices de la tupla Field
KEY, ENV, DEFAULT, TYPE, SECRET, LABEL, CHOICES = range(7)


def _cast(raw, typ):
    if typ == "int":
        return int(raw)
    if typ == "float":
        return float(raw)
    if typ == "bool":
        return str(raw).strip().lower() in ("1", "true", "yes", "on")
    return str(raw)


def env_present(env_var) -> bool:
    val = os.environ.get(env_var)
    return val is not None and val.strip() != ""


def is_locked(field) -> bool:
    """True si el operador fijó el campo en .env (queda global / solo lectura)."""
    return env_present(field[ENV])


def env_raw(field):
    return os.environ.get(field[ENV], "")


def user_data(user):
    if user is None or not getattr(user, "is_authenticated", False):
        return {}
    cfg = getattr(user, "config", None)
    return cfg.data if cfg else {}


def resolve(fields, user=None) -> dict:
    """Valor efectivo de cada campo (.env > usuario > default)."""
    data = user_data(user)
    out = {}
    for f in fields:
        if is_locked(f):
            raw = env_raw(f)
        elif f[KEY] in data and str(data[f[KEY]]).strip() != "":
            raw = data[f[KEY]]
        else:
            raw = f[DEFAULT]
        try:
            out[f[KEY]] = _cast(raw, f[TYPE])
        except (ValueError, TypeError):
            out[f[KEY]] = _cast(f[DEFAULT], f[TYPE])
    return out


def editable(fields, user=None):
    """Campos que el usuario puede editar (no bloqueados por .env), con su valor."""
    data = user_data(user)
    out = []
    for f in fields:
        if is_locked(f):
            continue
        out.append({
            "key": f[KEY], "label": f[LABEL], "type": f[TYPE], "secret": f[SECRET],
            "choices": f[CHOICES], "value": data.get(f[KEY], ""), "default": f[DEFAULT],
        })
    return out


def locked(fields):
    """Campos fijados por el operador en .env (para mostrar solo lectura)."""
    return [
        {"key": f[KEY], "label": f[LABEL], "value": "••••••" if f[SECRET] else env_raw(f)}
        for f in fields if is_locked(f)
    ]


def save_user_fields(user, fields, post):
    """Guarda en UserConfig los campos editables enviados (respeta secretos vacíos)."""
    from accounts.models import UserConfig

    cfg, _ = UserConfig.objects.get_or_create(user=user)
    for f in fields:
        if is_locked(f):
            continue
        submitted = post.get(f[KEY], "")
        if f[SECRET]:
            if submitted.strip() == "":      # vacío = mantener el guardado
                continue
            if submitted == "__CLEAR__":
                cfg.data.pop(f[KEY], None)
                continue
        cfg.data[f[KEY]] = submitted.strip()
    cfg.save(update_fields=["data"])


class Capability:
    """Función activable por flag en .env, con campos de conexión en cascada."""

    def __init__(self, key, flag_env, fields, required=(), label=""):
        self.key = key
        self.flag_env = flag_env
        self.fields = fields
        self.required = list(required)
        self.label = label

    def enabled(self) -> bool:
        return _cast(os.environ.get(self.flag_env, "0"), "bool")

    def required_all_in_env(self) -> bool:
        by_key = {f[KEY]: f for f in self.fields}
        return all(is_locked(by_key[k]) for k in self.required) and bool(self.required)

    def needs_user_config(self, user) -> bool:
        """True si está activa pero la conexión no está completa en .env → la pone el usuario."""
        return self.enabled() and not self.required_all_in_env()

    def configured(self, user) -> bool:
        vals = resolve(self.fields, user)
        return all(str(vals.get(k, "")).strip() != "" for k in self.required)

    def resolve(self, user=None):
        return resolve(self.fields, user)

    def editable_fields(self, user=None):
        return editable(self.fields, user)

    def locked_fields(self):
        return locked(self.fields)
