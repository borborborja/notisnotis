"""Capacidad 'digest email' sobre el patrón de cascada (notisnotis.optconfig).

- Flag de activación: DIGEST_ENABLED (true/false en .env).
- Conexión SMTP: campos en cascada (.env global > usuario > default).
- Preferencias del digest: SIEMPRE por usuario (frecuencia/hora/email/qué incluir).
"""
from __future__ import annotations

from notisnotis.optconfig import Capability, resolve, save_user_fields

# Conexión SMTP (cascada): si el operador la fija en .env → global; si no, la pone el usuario.
SMTP_FIELDS = [
    ("smtp_host", "SMTP_HOST", "", "str", False, "Servidor SMTP", None),
    ("smtp_port", "SMTP_PORT", "587", "int", False, "Puerto", None),
    ("smtp_user", "SMTP_USER", "", "str", False, "Usuario SMTP", None),
    ("smtp_password", "SMTP_PASSWORD", "", "str", True, "Contraseña SMTP", None),
    ("smtp_from", "SMTP_FROM", "", "str", False, "Remitente (From)", None),
    ("smtp_tls", "SMTP_USE_TLS", "1", "bool", False, "Usar TLS", None),
]

DIGEST = Capability(
    key="digest",
    flag_env="DIGEST_ENABLED",
    fields=SMTP_FIELDS,
    required=["smtp_host", "smtp_from"],
    label="Resumen por email (digest)",
)

# Web Push (VAPID). Las claves suelen ser globales del operador, pero siguen la cascade.
VAPID_FIELDS = [
    ("vapid_public", "VAPID_PUBLIC_KEY", "", "str", False, "Clave pública VAPID", None),
    ("vapid_private", "VAPID_PRIVATE_KEY", "", "str", True, "Clave privada VAPID", None),
    ("vapid_email", "VAPID_ADMIN_EMAIL", "", "str", False, "Email admin VAPID (mailto)", None),
]

WEBPUSH = Capability(
    key="webpush",
    flag_env="WEBPUSH_ENABLED",
    fields=VAPID_FIELDS,
    required=["vapid_public", "vapid_private"],
    label="Notificaciones push",
)

# Preferencias personales del digest (siempre por usuario, nunca .env).
FREQUENCIES = [("daily", "Diario"), ("weekly", "Semanal")]


def digest_prefs(user):
    cfg = getattr(user, "config", None)
    data = cfg.data if cfg else {}
    return {
        "optin": data.get("digest_optin") == "1",
        "frequency": data.get("digest_frequency", "daily"),
        "hour": int(data.get("digest_hour", 8) or 8),
        "email": data.get("digest_email", "") or (user.email or ""),
        "include_blindspots": data.get("digest_blindspots", "1") == "1",
        "webhook_url": data.get("webhook_url", ""),
    }


def save_digest_prefs(user, post):
    from accounts.models import UserConfig

    cfg, _ = UserConfig.objects.get_or_create(user=user)
    cfg.data["digest_optin"] = "1" if post.get("digest_optin") == "1" else "0"
    cfg.data["digest_frequency"] = post.get("digest_frequency", "daily")
    try:
        cfg.data["digest_hour"] = max(0, min(23, int(post.get("digest_hour", 8))))
    except (TypeError, ValueError):
        cfg.data["digest_hour"] = 8
    cfg.data["digest_email"] = post.get("digest_email", "").strip()
    cfg.data["digest_blindspots"] = "1" if post.get("digest_blindspots") == "1" else "0"
    cfg.data["webhook_url"] = post.get("webhook_url", "").strip()
    cfg.save(update_fields=["data"])
    # Guarda también la conexión SMTP si el usuario la rellenó (campos no bloqueados).
    save_user_fields(user, SMTP_FIELDS, post)


def smtp_settings(user):
    """Config SMTP efectiva para el usuario (.env > usuario > default)."""
    return resolve(SMTP_FIELDS, user)
