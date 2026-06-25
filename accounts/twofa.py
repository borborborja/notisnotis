"""Vistas de 2FA (TOTP) con códigos de recuperación.

Flujo:
  - setup (GET): muestra QR + secreto de un dispositivo TOTP sin confirmar.
  - setup (POST confirm): valida un código → confirma el dispositivo, genera 10
    códigos de recuperación de un solo uso y los muestra UNA vez.
  - verify: reto en el login para usuarios con dispositivo confirmado.
  - disable / recovery: desactivar 2FA y regenerar códigos.

Gateado por la función `twofa` (ver features/registry.py). El refuerzo del reto lo
hace accounts.middleware.Require2FAMiddleware.
"""
from __future__ import annotations

import io

import qrcode
import qrcode.image.svg
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from django_otp import login as otp_login
from django_otp import match_token
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

from features.decorators import feature_required

RECOVERY_COUNT = 10


def _svg_qr(data: str) -> str:
    """QR en SVG (sin Pillow) para incrustar inline en la plantilla."""
    img = qrcode.make(data, image_factory=qrcode.image.svg.SvgPathImage)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode()


def _confirmed_totp(user):
    return TOTPDevice.objects.filter(user=user, confirmed=True).first()


def _generate_recovery_codes(user):
    """(Re)genera los códigos de recuperación; devuelve la lista en claro (una vez)."""
    device, _ = StaticDevice.objects.get_or_create(user=user, name="recovery")
    device.token_set.all().delete()
    codes = []
    for _ in range(RECOVERY_COUNT):
        code = StaticToken.random_token()
        device.token_set.create(token=code)
        codes.append(code)
    device.confirmed = True
    device.save()
    return codes


@login_required
@feature_required("twofa")
def setup(request):
    # Si ya está activo, mostramos el panel de gestión.
    if _confirmed_totp(request.user):
        return render(request, "accounts/twofa_manage.html")

    # Dispositivo sin confirmar (reutilizamos uno pendiente o creamos uno limpio).
    device = TOTPDevice.objects.filter(user=request.user, confirmed=False).first()
    if device is None:
        device = TOTPDevice.objects.create(user=request.user, confirmed=False, name="default")

    if request.method == "POST":
        token = request.POST.get("token", "").strip()
        if device.verify_token(token):
            device.confirmed = True
            device.save()
            codes = _generate_recovery_codes(request.user)
            otp_login(request, device)  # deja la sesión verificada tras activar
            return render(request, "accounts/twofa_recovery.html", {"codes": codes, "fresh": True})
        messages.error(request, "Código incorrecto. Vuelve a intentarlo.")

    return render(request, "accounts/twofa_setup.html", {
        "qr_svg": _svg_qr(device.config_url),
        "secret": device.key,
    })


@login_required
@require_POST
@feature_required("twofa")
def disable(request):
    TOTPDevice.objects.filter(user=request.user).delete()
    StaticDevice.objects.filter(user=request.user).delete()
    messages.success(request, "Verificación en dos pasos desactivada.")
    return redirect("account_settings_tab", tab="account")


@login_required
@require_POST
@feature_required("twofa")
def regenerate_recovery(request):
    if not _confirmed_totp(request.user):
        return redirect("account_settings_tab", tab="account")
    codes = _generate_recovery_codes(request.user)
    return render(request, "accounts/twofa_recovery.html", {"codes": codes, "fresh": False})


@login_required
def verify(request):
    """Reto de 2FA tras el login con contraseña (TOTP o código de recuperación)."""
    if request.user.is_verified():
        return redirect("stories:home")
    if request.method == "POST":
        token = request.POST.get("token", "").strip()
        device = match_token(request.user, token)  # prueba TOTP y códigos estáticos
        if device is not None:
            otp_login(request, device)
            return redirect(request.GET.get("next") or "stories:home")
        messages.error(request, "Código incorrecto.")
    return render(request, "accounts/twofa_verify.html")
