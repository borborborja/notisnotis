"""Gestión: suscribir/editar/borrar feeds, categorías y OPML import/export."""
from __future__ import annotations

from django.http import HttpResponse
from django.views.decorators.http import require_GET, require_http_methods

from .auth import api_token
from .helpers import as_int, body_json, err, ok
from .serializers import category_dict, feed_dict


@api_token
@require_http_methods(["POST"])
def subscribe(request):
    """POST {url} (descubre el feed) o {feed_url} directo, +category_id?, +kind?."""
    from feeds.views import _create_feed
    from feeds.discovery import discover_feeds, feed_title
    from feeds.models import Category

    data = body_json(request)
    feed_url = data.get("feed_url")
    if not feed_url:
        url = (data.get("url") or "").strip()
        if not url:
            return err("bad_request", "Indica 'url' o 'feed_url'.")
        candidates = discover_feeds(url)
        if not candidates:
            return err("no_feed", "No se encontró ningún feed en esa URL.", status=404)
        feed_url = candidates[0]["url"] if isinstance(candidates[0], dict) else candidates[0]
    category = None
    if data.get("category_id"):
        category = Category.objects.filter(user=request.api_user, id=data["category_id"]).first()
    feed, created = _create_feed(request.api_user, feed_url,
                                 data.get("title") or feed_title(feed_url),
                                 category=category, kind=data.get("kind"))
    return ok(feed_dict(feed), created=created)


@api_token
@require_http_methods(["PATCH", "DELETE"])
def feed_detail(request, pk):
    from feeds.models import Category, Feed

    f = Feed.objects.filter(user=request.api_user, pk=pk).select_related("source").first()
    if not f:
        return err("not_found", "Feed no encontrado.", status=404)
    if request.method == "DELETE":
        f.delete()
        return ok({"deleted": pk})
    data = body_json(request)
    fields = []
    if "title" in data:
        f.title = str(data["title"])[:500]; fields.append("title")
    if "enabled" in data:
        f.enabled = bool(data["enabled"]); fields.append("enabled")
    if "crawler" in data:
        f.crawler = bool(data["crawler"]); fields.append("crawler")
    if "category_id" in data:
        f.category = Category.objects.filter(user=request.api_user, id=data["category_id"]).first()
        fields.append("category")
    if fields:
        f.save(update_fields=fields)
    return ok(feed_dict(f))


@api_token
@require_http_methods(["GET", "POST"])
def categories(request):
    from feeds.models import Category

    if request.method == "GET":
        return ok([category_dict(c) for c in Category.objects.filter(user=request.api_user)])
    name = (body_json(request).get("name") or "").strip()[:200]
    if not name:
        return err("bad_request", "Falta 'name'.")
    c, _ = Category.objects.get_or_create(user=request.api_user, name=name)
    return ok(category_dict(c))


@api_token
@require_http_methods(["PATCH", "DELETE"])
def category_detail(request, pk):
    from feeds.models import Category

    c = Category.objects.filter(user=request.api_user, pk=pk).first()
    if not c:
        return err("not_found", "Categoría no encontrada.", status=404)
    if request.method == "DELETE":
        c.delete()
        return ok({"deleted": pk})
    data = body_json(request)
    fields = []
    if "name" in data:
        c.name = str(data["name"])[:200]; fields.append("name")
    if "position" in data and as_int(data["position"]) is not None:
        c.position = as_int(data["position"]); fields.append("position")
    if fields:
        c.save(update_fields=fields)
    return ok(category_dict(c))


@api_token
@require_http_methods(["POST"])
def opml_import(request):
    """Cuerpo: OPML crudo (Content-Type xml) o JSON {opml, kind?}."""
    from feeds.opml import import_opml_for_user

    ctype = request.META.get("CONTENT_TYPE", "")
    if "json" in ctype:
        data = body_json(request)
        content, kind = data.get("opml", ""), data.get("kind", "rss")
    else:
        content, kind = request.body.decode("utf-8", "ignore"), request.GET.get("kind", "rss")
    if not content.strip():
        return err("bad_request", "OPML vacío.")
    n = import_opml_for_user(request.api_user, content, kind=kind)
    return ok({"imported": n})


@api_token
@require_GET
def opml_export(request):
    from feeds.models import Feed
    from xml.sax.saxutils import escape

    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<opml version="1.0">',
             "<head><title>facet.news</title></head>", "<body>"]
    for f in Feed.objects.filter(user=request.api_user).select_related("source"):
        title = escape(f.title or f.source.name)
        lines.append(f'<outline type="rss" text="{title}" title="{title}" '
                     f'xmlUrl="{escape(f.url)}"/>')
    lines += ["</body>", "</opml>"]
    return HttpResponse("\n".join(lines), content_type="text/x-opml; charset=utf-8")
