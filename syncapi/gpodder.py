"""API gpodder (mygpo) para sincronizar podcasts con AntennaPod y otros clientes.

Auth: HTTP Basic con usuario + app-password de SyncCredential. Mapea suscripciones a Feed
(kind=podcast) y las acciones de reproducción a Article.play_position / is_read.
"""
from __future__ import annotations

import json
from datetime import timezone as _tz

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from articles.models import Article
from feeds.models import Feed
from features.modules import module_enabled

from .auth import user_from_basic
from .models import GpodderDevice


def _auth(request, username=None):
    if not settings.GPODDER_ENABLED:
        return None
    user = user_from_basic(request, username)
    if user and not module_enabled(user, "podcasts"):
        return None
    return user


def _unauth():
    resp = JsonResponse({"error": "auth"}, status=401)
    resp["WWW-Authenticate"] = 'Basic realm="gpodder"'
    return resp


def _now_ts():
    return int(timezone.now().timestamp())


def _body_json(request):
    try:
        return json.loads(request.body.decode("utf-8") or "[]")
    except (ValueError, UnicodeDecodeError):
        return []


def _podcast_feeds(user):
    return Feed.objects.filter(user=user, kind__in=["podcast", "youtube"])


@csrf_exempt
def login(request, username):
    user = _auth(request, username)
    return JsonResponse({}) if user else _unauth()


@csrf_exempt
def devices(request, username):
    user = _auth(request, username)
    if not user:
        return _unauth()
    subs = _podcast_feeds(user).count()
    data = [{"id": d.device_id, "caption": d.caption or d.device_id, "type": d.type,
             "subscriptions": subs}
            for d in user.gpodder_devices.all()]
    return JsonResponse(data, safe=False)


@csrf_exempt
def device_update(request, username, deviceid):
    user = _auth(request, username)
    if not user:
        return _unauth()
    payload = _body_json(request) if request.body else {}
    dev, _ = GpodderDevice.objects.get_or_create(user=user, device_id=deviceid)
    if isinstance(payload, dict):
        dev.caption = (payload.get("caption") or dev.caption)[:255]
        dev.type = (payload.get("type") or dev.type)[:32]
        dev.save()
    return JsonResponse({})


@csrf_exempt
def subscriptions(request, username, deviceid):
    """GET ?since= → cambios; POST {add,remove} → aplica."""
    user = _auth(request, username)
    if not user:
        return _unauth()
    GpodderDevice.objects.get_or_create(user=user, device_id=deviceid)

    if request.method == "POST":
        payload = _body_json(request)
        add = payload.get("add", []) if isinstance(payload, dict) else []
        remove = payload.get("remove", []) if isinstance(payload, dict) else []
        _apply_subscriptions(user, add, remove)
        return JsonResponse({"timestamp": _now_ts(), "update_urls": []})

    since = request.GET.get("since", "0")
    add = []
    if since in ("", "0"):
        add = list(_podcast_feeds(user).values_list("url", flat=True))
    return JsonResponse({"add": add, "remove": [], "timestamp": _now_ts()})


@csrf_exempt
def subscriptions_file(request, username, deviceid, fmt):
    """GET/PUT /subscriptions/<user>/<dev>.<fmt> (txt/json/opml)."""
    user = _auth(request, username)
    if not user:
        return _unauth()
    GpodderDevice.objects.get_or_create(user=user, device_id=deviceid)

    if request.method == "PUT":
        urls = _parse_urls(request.body.decode("utf-8", "replace"), fmt)
        current = set(_podcast_feeds(user).values_list("url", flat=True))
        _apply_subscriptions(user, [u for u in urls if u not in current],
                             [u for u in current if u not in set(urls)])
        return HttpResponse(status=200)

    urls = list(_podcast_feeds(user).values_list("url", flat=True))
    if fmt == "json":
        return JsonResponse(urls, safe=False)
    if fmt == "opml":
        items = "".join(f'<outline type="rss" xmlUrl="{u}"/>' for u in urls)
        opml = f'<?xml version="1.0"?><opml version="2.0"><body>{items}</body></opml>'
        return HttpResponse(opml, content_type="text/x-opml")
    return HttpResponse("\n".join(urls), content_type="text/plain")


@csrf_exempt
def episodes(request, username):
    """POST [acciones] → aplica; GET ?since= → acciones de reproducción."""
    user = _auth(request, username)
    if not user:
        return _unauth()

    if request.method == "POST":
        for act in _body_json(request) or []:
            _apply_episode_action(user, act)
        return JsonResponse({"timestamp": _now_ts(), "update_urls": []})

    since = request.GET.get("since", "0")
    qs = Article.objects.filter(feed__user=user, feed__kind__in=["podcast", "youtube"],
                                play_updated_at__isnull=False).select_related("feed")
    try:
        since_i = int(since)
    except (TypeError, ValueError):
        since_i = 0
    if since_i > 0:
        since_dt = timezone.datetime.fromtimestamp(since_i, tz=_tz.utc)
        qs = qs.filter(play_updated_at__gt=since_dt)
    actions = []
    for a in qs[:1000]:
        actions.append({
            "podcast": a.feed.url, "episode": a.enclosure_url, "action": "play",
            "position": a.play_position, "total": a.duration,
            "timestamp": a.play_updated_at.strftime("%Y-%m-%dT%H:%M:%S"),
        })
    return JsonResponse({"actions": actions, "timestamp": _now_ts()})


# ---------------- helpers ----------------

def _apply_subscriptions(user, add, remove):
    from feeds.views import _create_feed
    for url in add:
        if url:
            _create_feed(user, url, "", kind="podcast")
    for url in remove:
        _podcast_feeds(user).filter(url=url).delete()


def _parse_urls(text, fmt):
    text = text.strip()
    if fmt == "json":
        try:
            data = json.loads(text)
            return [u for u in data if isinstance(u, str)]
        except ValueError:
            return []
    if fmt == "opml" or text.startswith("<"):
        import re
        return re.findall(r'xmlUrl="([^"]+)"', text)
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _apply_episode_action(user, act):
    if not isinstance(act, dict):
        return
    ep_url = act.get("episode")
    if not ep_url:
        return
    art = (Article.objects.filter(feed__user=user, enclosure_url=ep_url)
           .select_related("feed").first())
    if not art:
        return
    action = (act.get("action") or "").lower()
    fields = []
    if action == "play":
        pos = int(act.get("position") or 0)
        total = int(act.get("total") or 0)
        art.play_position = max(0, pos)
        fields.append("play_position")
        if total and not art.duration:
            art.duration = total
            fields.append("duration")
        if total and pos >= total - 30:
            art.is_read = True
            art.read_at = timezone.now()
            art.play_position = 0
            fields += ["is_read", "read_at"]
    elif action in ("delete", "new"):
        art.is_read = (action == "delete")
        fields.append("is_read")
    if fields:
        art.play_updated_at = timezone.now()
        fields.append("play_updated_at")
        art.save(update_fields=fields)
