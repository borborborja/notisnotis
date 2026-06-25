"""Google Reader API (subconjunto). Compatible con NetNewsWire / Reeder / FluentReader."""
from __future__ import annotations

import time

from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from articles.models import Article
from feeds.models import Category, Feed

from .auth import user_from_greader
from .models import SyncCredential

READ = "user/-/state/com.google/read"
STARRED = "user/-/state/com.google/starred"
READING_LIST = "user/-/state/com.google/reading-list"


# --------------------------------------------------------------------------- helpers
def _usec(dt):
    return int(time.mktime(dt.timetuple()) * 1_000_000) if dt else 0


def _long_id(pk):
    return f"tag:google.com,2005:reader/item/{pk:016x}"


def parse_item_id(s):
    s = (s or "").strip()
    if "reader/item/" in s:
        s = s.rsplit("/", 1)[-1]
    if s.lstrip("-").isdigit():
        return int(s)
    try:
        return int(s, 16)
    except ValueError:
        return None


def _require(request):
    return user_from_greader(request)


def _articles_for_stream(user, stream):
    qs = Article.objects.filter(feed__user=user).select_related("source", "feed")
    if stream == STARRED:
        return qs.filter(is_saved=True)
    if stream == READ:
        return qs.filter(is_read=True)
    if stream and stream.startswith("feed/"):
        return qs.filter(feed_id=stream.split("/", 1)[1])
    if stream and "/label/" in stream:
        label = stream.split("/label/", 1)[1]
        from django.db.models import Q

        return qs.filter(Q(feed__category__name=label) | Q(tags__name=label)).distinct()
    return qs  # reading-list / desconocido = todos


# --------------------------------------------------------------------------- auth
@csrf_exempt
def client_login(request):
    email = request.POST.get("Email") or request.GET.get("Email", "")
    passwd = request.POST.get("Passwd") or request.GET.get("Passwd", "")
    cred = SyncCredential.objects.select_related("user").filter(user__username=email).first()
    if not cred or passwd != cred.password:
        return HttpResponse("Error=BadAuthentication", status=403)
    body = f"SID={cred.token}\nLSID={cred.token}\nAuth={cred.token}\n"
    return HttpResponse(body, content_type="text/plain")


@csrf_exempt
def token(request):
    user = _require(request)
    if not user:
        return HttpResponseForbidden("")
    return HttpResponse(user.sync_credential.token, content_type="text/plain")


def user_info(request):
    user = _require(request)
    if not user:
        return HttpResponseForbidden("")
    return JsonResponse({
        "userId": str(user.id), "userName": user.get_username(),
        "userProfileId": str(user.id), "userEmail": user.email or "",
    })


# --------------------------------------------------------------------------- listas
def subscription_list(request):
    user = _require(request)
    if not user:
        return HttpResponseForbidden("")
    subs = []
    for f in Feed.objects.filter(user=user).select_related("source", "category"):
        cats = []
        if f.category:
            cats = [{"id": f"user/-/label/{f.category.name}", "label": f.category.name}]
        subs.append({
            "id": f"feed/{f.id}", "title": f.title or f.source.name,
            "categories": cats, "url": f.url, "htmlUrl": f"https://{f.source.domain}",
            "iconUrl": "",
        })
    return JsonResponse({"subscriptions": subs})


def tag_list(request):
    user = _require(request)
    if not user:
        return HttpResponseForbidden("")
    from articles.models import Tag

    tags = [{"id": STARRED, "sortid": "starred"}]
    names = set(Category.objects.filter(user=user).values_list("name", flat=True))
    names |= set(Tag.objects.filter(user=user).values_list("name", flat=True))
    for name in sorted(names):
        tags.append({"id": f"user/-/label/{name}", "sortid": name})
    return JsonResponse({"tags": tags})


def unread_count(request):
    user = _require(request)
    if not user:
        return HttpResponseForbidden("")
    counts = []
    total = 0
    for f in Feed.objects.filter(user=user):
        n = Article.objects.filter(feed=f, is_read=False).count()
        if n:
            counts.append({"id": f"feed/{f.id}", "count": n, "newestItemTimestampUsec": "0"})
            total += n
    counts.insert(0, {"id": READING_LIST, "count": total, "newestItemTimestampUsec": "0"})
    return JsonResponse({"max": total, "unreadcounts": counts})


# --------------------------------------------------------------------------- streams
def stream_items_ids(request):
    user = _require(request)
    if not user:
        return HttpResponseForbidden("")
    stream = request.GET.get("s", READING_LIST)
    exclude = request.GET.get("xt", "")
    try:
        n = min(int(request.GET.get("n", 1000)), 10000)
    except ValueError:
        n = 1000
    offset = int(request.GET.get("c", 0) or 0)

    qs = _articles_for_stream(user, stream)
    if exclude == READ:
        qs = qs.filter(is_read=False)
    elif exclude == STARRED:
        qs = qs.filter(is_saved=False)
    qs = qs.order_by("-id")
    rows = list(qs.values_list("id", "published_at", "fetched_at")[offset:offset + n + 1])
    refs = [
        {"id": str(pk), "timestampUsec": str(_usec(pub or fetched))}
        for pk, pub, fetched in rows[:n]
    ]
    out = {"itemRefs": refs}
    if len(rows) > n:
        out["continuation"] = str(offset + n)
    return JsonResponse(out)


@csrf_exempt
def stream_items_contents(request):
    user = _require(request)
    if not user:
        return HttpResponseForbidden("")
    raw_ids = request.POST.getlist("i") or request.GET.getlist("i")
    pks = [parse_item_id(x) for x in raw_ids]
    pks = [p for p in pks if p is not None]
    arts = Article.objects.filter(feed__user=user, id__in=pks).select_related("source", "feed")
    items = [_content_item(a, user) for a in arts]
    return JsonResponse({"id": "user/-/state/com.google/reading-list", "items": items})


def stream_contents(request, stream=""):
    user = _require(request)
    if not user:
        return HttpResponseForbidden("")
    qs = _articles_for_stream(user, stream or request.GET.get("s", READING_LIST)).order_by("-id")[:50]
    return JsonResponse({"items": [_content_item(a, user) for a in qs]})


def _content_item(a, user=None):
    from .curation import enriched_html

    cats = [READING_LIST]
    if a.is_read:
        cats.append(READ)
    if a.is_saved:
        cats.append(STARRED)
    return {
        "id": _long_id(a.id),
        "title": a.title,
        "published": int(time.mktime((a.published_at or a.fetched_at).timetuple())),
        "updated": int(time.mktime((a.published_at or a.fetched_at).timetuple())),
        "canonical": [{"href": a.url}],
        "alternate": [{"href": a.url, "type": "text/html"}],
        "categories": cats,
        "origin": {"streamId": f"feed/{a.feed_id}", "title": a.source.name},
        "summary": {"content": enriched_html(a, user) if user else a.best_text},
        "author": "",
    }


# --------------------------------------------------------------------------- escritura
@csrf_exempt
def edit_tag(request):
    user = _require(request)
    if not user:
        return HttpResponseForbidden("")
    add = request.POST.getlist("a")
    remove = request.POST.getlist("r")
    pks = [parse_item_id(x) for x in request.POST.getlist("i")]
    pks = [p for p in pks if p is not None]
    arts = Article.objects.filter(feed__user=user, id__in=pks)
    now = timezone.now()
    if READ in add:
        arts.update(is_read=True, read_at=now)
    if READ in remove:
        arts.update(is_read=False, read_at=None)
    if STARRED in add:
        arts.update(is_saved=True)
    if STARRED in remove:
        arts.update(is_saved=False)
    # Etiquetas de usuario: user/-/label/<name>
    from articles.models import Tag

    for tagspec in add:
        if "/label/" in tagspec:
            tag, _ = Tag.objects.get_or_create(user=user, name=tagspec.split("/label/", 1)[1])
            for a in arts:
                a.tags.add(tag)
    for tagspec in remove:
        if "/label/" in tagspec:
            t = Tag.objects.filter(user=user, name=tagspec.split("/label/", 1)[1]).first()
            if t:
                for a in arts:
                    a.tags.remove(t)
    return HttpResponse("OK")


@csrf_exempt
def mark_all_as_read(request):
    user = _require(request)
    if not user:
        return HttpResponseForbidden("")
    stream = request.POST.get("s", READING_LIST)
    qs = _articles_for_stream(user, stream).filter(is_read=False)
    ts = request.POST.get("ts")
    if ts:
        try:
            cutoff = timezone.datetime.fromtimestamp(int(ts) / 1_000_000, tz=timezone.utc)
            qs = qs.filter(published_at__lte=cutoff)
        except (ValueError, OSError):
            pass
    qs.update(is_read=True, read_at=timezone.now())
    return HttpResponse("OK")
