"""Refuerzo del segundo factor (2FA).

Si un usuario autenticado tiene un dispositivo TOTP CONFIRMADO pero aún no ha
superado el reto OTP en esta sesión, lo redirigimos a la pantalla de verificación
y bloqueamos el resto de la app. Requiere `django_otp.middleware.OTPMiddleware`
antes (aporta `request.user.is_verified()`).
"""
from __future__ import annotations

from django.shortcuts import redirect

# Rutas accesibles sin haber completado el 2FA (el propio reto, salir, estáticos).
_ALLOWED_PREFIXES = ("/accounts/2fa/verify", "/accounts/logout", "/sw.js", "/static/", "/api/")


class Require2FAMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and not user.is_verified():
            from django_otp import user_has_device

            if user_has_device(user, confirmed=True):
                if not any(request.path.startswith(p) for p in _ALLOWED_PREFIXES):
                    return redirect("twofa_verify")
        return self.get_response(request)
