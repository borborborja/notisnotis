"""Envío de Web Push (VAPID). pywebpush requiere Python >= 3.10 (corre en Docker)."""
from __future__ import annotations

import json

from .config import WEBPUSH


def available():
    try:
        import pywebpush  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def send_push(user, title, body, url="/"):
    """Envía una notificación a todas las suscripciones del usuario. Devuelve nº enviadas."""
    if not WEBPUSH.enabled():
        return 0
    cfg = WEBPUSH.resolve(user)
    if not cfg["vapid_private"] or not cfg["vapid_public"]:
        return 0
    try:
        from pywebpush import WebPushException, webpush
    except Exception:  # noqa: BLE001  (Python < 3.10 o dependencia ausente)
        return 0

    payload = json.dumps({"title": title, "body": body, "url": url})
    claims = {"sub": f"mailto:{cfg['vapid_email'] or 'admin@example.com'}"}
    sent = 0
    for sub in user.push_subscriptions.all():
        try:
            webpush(
                subscription_info=sub.as_subscription_info(),
                data=payload,
                vapid_private_key=cfg["vapid_private"],
                vapid_claims=dict(claims),
            )
            sent += 1
        except WebPushException as exc:
            # 404/410 = suscripción muerta → eliminar.
            if getattr(exc, "response", None) is not None and exc.response.status_code in (404, 410):
                sub.delete()
        except Exception:  # noqa: BLE001
            pass
    return sent
