"""Auth (login→token), identidad del usuario y estado de módulos."""
from __future__ import annotations

from django.contrib.auth import authenticate
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .auth import api_token
from .helpers import body_json, err, ok, server_time


@csrf_exempt
@require_POST
def auth_token(request):
    """POST {username, password, otp?} → {token}. Respeta 2FA si el usuario lo tiene."""
    data = body_json(request)
    user = authenticate(username=data.get("username", ""), password=data.get("password", ""))
    if user is None or not user.is_active:
        return err("invalid_credentials", "Usuario o contraseña incorrectos.", status=401)

    from django_otp import match_token, user_has_device

    if user_has_device(user, confirmed=True):
        otp = (data.get("otp") or "").strip()
        if not otp:
            return err("otp_required", "Este usuario tiene 2FA; envía 'otp'.", status=401)
        if not match_token(user, otp):
            return err("invalid_otp", "Código 2FA incorrecto.", status=401)

    from accounts.models import ApiToken

    tok = (ApiToken.objects.filter(user=user, name="app").first()
           or ApiToken.objects.create(user=user, name="app"))
    return ok({"token": tok.token, "user": user.get_username()})


def _modules(user):
    from features.modules import modules_state

    state = {m["module"]: m["enabled"] for m in modules_state(user)}
    state["rss"] = True
    return state


@api_token
@require_GET
def me(request):
    from articles.models import Article

    user = request.api_user
    arts = Article.objects.filter(feed__user=user)
    counts = {
        "unread": arts.filter(is_read=False).count(),
        "saved": arts.filter(is_saved=True).count(),
    }
    mods = _modules(user)
    if mods.get("podcasts"):
        from podcasts.models import QueueItem

        counts["queue"] = QueueItem.objects.filter(user=user).count()
    return ok({
        "user": user.get_username(),
        "modules": mods,
        "counts": counts,
        "server_time": server_time(),
    })


@api_token
@require_GET
def modules(request):
    return ok(_modules(request.api_user))
