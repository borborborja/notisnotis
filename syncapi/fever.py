"""Fever API (https://feedafever.com/api). Endpoint único para lectores tipo Reeder/Unread."""
from __future__ import annotations

import time

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from articles.models import Article
from feeds.models import Category, Feed

from .auth import user_from_fever

PAGE = 50


def _epoch(dt):
    return int(time.mktime(dt.timetuple())) if dt else 0


def _has(request, flag):
    return flag in request.GET or flag in request.POST


def _param(request, key, default=None):
    return request.GET.get(key, request.POST.get(key, default))


@csrf_exempt
@require_POST
def endpoint(request):
    user = user_from_fever(_param(request, "api_key", ""))
    last = Feed.objects.filter(user=user).order_by("-last_fetched").first() if user else None
    resp = {
        "api_version": 3,
        "auth": 1 if user else 0,
        "last_refreshed_on_time": _epoch(last.last_fetched) if last and last.last_fetched else _epoch(timezone.now()),
    }
    if not user:
        return JsonResponse({"api_version": 3, "auth": 0})

    # --- acciones de escritura ---
    mark = _param(request, "mark")
    if mark:
        _handle_mark(user, mark, _param(request, "as", ""), _param(request, "id"), _param(request, "before"))

    # --- lecturas ---
    if _has(request, "groups"):
        cats = list(Category.objects.filter(user=user))
        resp["groups"] = [{"id": c.id, "title": c.name} for c in cats]
        resp["feeds_groups"] = _feeds_groups(user)
    if _has(request, "feeds"):
        feeds = Feed.objects.filter(user=user).select_related("source")
        resp["feeds"] = [
            {
                "id": f.id, "favicon_id": f.source_id if f.source.favicon else 0,
                "title": f.title or f.source.name, "url": f.url,
                "site_url": f"https://{f.source.domain}", "is_spark": 0,
                "last_updated_on_time": _epoch(f.last_fetched),
            }
            for f in feeds
        ]
        resp["feeds_groups"] = _feeds_groups(user)
    if _has(request, "favicons"):
        resp["favicons"] = [
            {"id": s_id, "data": fav}
            for s_id, fav in Feed.objects.filter(user=user, source__favicon__gt="")
            .values_list("source_id", "source__favicon").distinct()
        ]
    if _has(request, "items"):
        resp.update(_items(request, user))
    if _has(request, "unread_item_ids"):
        ids = Article.objects.filter(feed__user=user, is_read=False).values_list("id", flat=True)
        resp["unread_item_ids"] = ",".join(map(str, ids))
    if _has(request, "saved_item_ids"):
        ids = Article.objects.filter(feed__user=user, is_saved=True).values_list("id", flat=True)
        resp["saved_item_ids"] = ",".join(map(str, ids))
    if _has(request, "links"):
        resp["links"] = []

    return JsonResponse(resp)


def _feeds_groups(user):
    out = []
    for c in Category.objects.filter(user=user):
        ids = list(Feed.objects.filter(user=user, category=c).values_list("id", flat=True))
        if ids:
            out.append({"group_id": c.id, "feed_ids": ",".join(map(str, ids))})
    return out


def _items(request, user):
    from .curation import visible_articles

    qs = visible_articles(user).select_related("source")
    with_ids = _param(request, "with_ids")
    if with_ids:
        ids = [int(x) for x in with_ids.split(",") if x.strip().isdigit()]
        qs = qs.filter(id__in=ids).order_by("id")
    elif _param(request, "max_id"):
        qs = qs.filter(id__lt=int(_param(request, "max_id"))).order_by("-id")[:PAGE]
        qs = sorted(qs, key=lambda a: a.id)
    else:
        since = int(_param(request, "since_id", 0))
        qs = qs.filter(id__gt=since).order_by("id")[:PAGE]
    from .curation import enriched_html

    items = [
        {
            "id": a.id, "feed_id": a.feed_id, "title": a.title, "author": "",
            "html": enriched_html(a, user), "url": a.url,
            "is_saved": 1 if a.is_saved else 0, "is_read": 1 if a.is_read else 0,
            "created_on_time": _epoch(a.published_at or a.fetched_at),
        }
        for a in qs
    ]
    total = Article.objects.filter(feed__user=user).count()
    return {"items": items, "total_items": total}


def _handle_mark(user, mark, as_, oid, before):
    if not oid:
        return
    now = timezone.now()
    if mark == "item":
        art = Article.objects.filter(feed__user=user, id=oid).first()
        if not art:
            return
        if as_ == "read":
            art.is_read = True; art.read_at = now
        elif as_ == "unread":
            art.is_read = False; art.read_at = None
        elif as_ == "saved":
            art.is_saved = True
        elif as_ == "unsaved":
            art.is_saved = False
        art.save()
    elif mark in ("feed", "group") and as_ == "read":
        qs = Article.objects.filter(feed__user=user, is_read=False)
        if mark == "feed":
            qs = qs.filter(feed_id=oid)
        elif oid not in ("0", "", None):
            qs = qs.filter(feed__category_id=oid)
        if before:
            qs = qs.filter(published_at__lte=timezone.datetime.fromtimestamp(int(before), tz=timezone.utc))
        qs.update(is_read=True, read_at=now)
