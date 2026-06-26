"""Lector RSS: feeds, categorías, tags, artículos y estado (leído/guardado/tags)."""
from __future__ import annotations

from django.db.models import Count, Q
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from .auth import api_token
from .helpers import body_json, err, make_cursor, ok, param, parse_cursor, parse_since
from .serializers import article_dict, category_dict, feed_dict, tag_dict

MAX_LIMIT = 200


@api_token
@require_GET
def feeds(request):
    from feeds.models import Feed

    qs = (Feed.objects.filter(user=request.api_user).select_related("source")
          .annotate(unread=Count("articles", filter=Q(articles__is_read=False))))
    return ok([feed_dict(f, unread=f.unread) for f in qs])


@api_token
@require_GET
def categories(request):
    from feeds.models import Category

    qs = (Category.objects.filter(user=request.api_user)
          .annotate(unread=Count("feeds__articles",
                                 filter=Q(feeds__articles__is_read=False))))
    return ok([category_dict(c, unread=c.unread) for c in qs])


@api_token
@require_GET
def tags(request):
    from articles.models import Tag

    return ok([tag_dict(t) for t in Tag.objects.filter(user=request.api_user)])


def _article_qs(request):
    from articles.models import Article

    qs = (Article.objects.filter(feed__user=request.api_user)
          .select_related("source", "feed").prefetch_related("tags"))
    feed = param(request, "feed")
    category = param(request, "category")
    tag = param(request, "tag")
    q = param(request, "q")
    if feed:
        qs = qs.filter(feed_id=feed)
    if category:
        qs = qs.filter(feed__category_id=category)
    if tag:
        qs = qs.filter(tags__name=tag)
    if param(request, "unread") == "1":
        qs = qs.filter(is_read=False)
    if param(request, "saved") == "1":
        qs = qs.filter(is_saved=True)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(summary__icontains=q))
    since = parse_since(param(request, "since"))
    if since:
        qs = qs.filter(fetched_at__gt=since)
    return qs


@api_token
@require_GET
def articles(request):
    try:
        limit = min(int(param(request, "limit", "50")), MAX_LIMIT)
    except ValueError:
        limit = 50
    qs = _article_qs(request).order_by("-fetched_at", "-id")
    cur_dt, cur_id = parse_cursor(param(request, "cursor"))
    if cur_dt and cur_id:
        qs = qs.filter(Q(fetched_at__lt=cur_dt) | (Q(fetched_at=cur_dt) & Q(id__lt=cur_id)))
    rows = list(qs[: limit + 1])
    has_more = len(rows) > limit
    rows = rows[:limit]
    nxt = make_cursor(rows[-1].fetched_at, rows[-1].id) if (has_more and rows) else ""
    return ok([article_dict(a, user=request.api_user) for a in rows],
              cursor=nxt, has_more=has_more)


@api_token
@require_GET
def article_detail(request, pk):
    from articles.models import Article

    a = (Article.objects.filter(feed__user=request.api_user)
         .select_related("source", "feed").prefetch_related("tags").filter(pk=pk).first())
    if not a:
        return err("not_found", "Artículo no encontrado.", status=404)
    return ok(article_dict(a, user=request.api_user, full=True))


@api_token
@require_http_methods(["POST"])
def article_state(request, pk):
    """{read?: bool, saved?: bool} sobre un artículo."""
    from articles.models import Article

    a = Article.objects.filter(feed__user=request.api_user, pk=pk).first()
    if not a:
        return err("not_found", "Artículo no encontrado.", status=404)
    data = body_json(request)
    fields = []
    if "read" in data:
        a.is_read = bool(data["read"])
        a.read_at = timezone.now() if a.is_read else None
        fields += ["is_read", "read_at"]
    if "saved" in data:
        a.is_saved = bool(data["saved"])
        fields.append("is_saved")
    if fields:
        a.save(update_fields=fields)  # el override añade updated_at
    return ok(article_dict(a, user=request.api_user))


@api_token
@require_http_methods(["POST"])
def articles_state(request):
    """Estado en bloque: {ids|feed|category|older_than, read?, saved?}."""
    from articles.models import Article

    data = body_json(request)
    qs = Article.objects.filter(feed__user=request.api_user)
    if data.get("ids"):
        qs = qs.filter(id__in=data["ids"])
    elif data.get("feed"):
        qs = qs.filter(feed_id=data["feed"])
    elif data.get("category"):
        qs = qs.filter(feed__category_id=data["category"])
    else:
        return err("bad_request", "Indica ids, feed o category.")
    older = parse_since(data.get("older_than"))
    if older:
        qs = qs.filter(fetched_at__lt=older)
    now = timezone.now()
    changes = {"updated_at": now}
    if "read" in data:
        changes["is_read"] = bool(data["read"])
        changes["read_at"] = now if data["read"] else None
    if "saved" in data:
        changes["is_saved"] = bool(data["saved"])
    n = qs.update(**changes) if len(changes) > 1 else 0
    return ok({"updated": n})


@api_token
@require_http_methods(["POST", "DELETE"])
def article_tags(request, pk):
    """POST {name} añade tag; DELETE {name} lo quita."""
    from articles.models import Article, Tag

    a = Article.objects.filter(feed__user=request.api_user, pk=pk).first()
    if not a:
        return err("not_found", "Artículo no encontrado.", status=404)
    name = (body_json(request).get("name") or "").strip()[:100]
    if not name:
        return err("bad_request", "Falta 'name'.")
    if request.method == "POST":
        tag, _ = Tag.objects.get_or_create(user=request.api_user, name=name)
        a.tags.add(tag)
    else:
        a.tags.remove(*Tag.objects.filter(user=request.api_user, name=name))
    a.save(update_fields=["updated_at"])
    return ok(article_dict(a, user=request.api_user))
