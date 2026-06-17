import json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST

from .config import WEBPUSH
from .models import PushSubscription


@login_required
def push_key(request):
    """Clave pública VAPID para que el navegador se suscriba."""
    cfg = WEBPUSH.resolve(request.user)
    return JsonResponse({"enabled": WEBPUSH.enabled() and bool(cfg["vapid_public"]),
                         "key": cfg["vapid_public"]})


@login_required
@require_POST
def push_subscribe(request):
    try:
        data = json.loads(request.body or "{}")
        endpoint = data["endpoint"]
        keys = data["keys"]
    except (ValueError, KeyError):
        return HttpResponse(status=400)
    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={"user": request.user, "p256dh": keys.get("p256dh", ""), "auth": keys.get("auth", "")},
    )
    return HttpResponse(status=204)


@login_required
@require_POST
def push_unsubscribe(request):
    try:
        endpoint = json.loads(request.body or "{}").get("endpoint", "")
    except ValueError:
        endpoint = ""
    PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
    return HttpResponse(status=204)
