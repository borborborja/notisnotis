"""Delta-sync: devuelve lo cambiado desde un cursor, con contenido + estado.

El cliente nunca re-descarga de la fuente: el servidor sirve lo que ya tiene. Primera
llamada sin `since` = sync completa; luego `?since=<server_time anterior>` trae solo deltas.
"""
from __future__ import annotations

from django.db.models import Q
from django.views.decorators.http import require_GET

from .auth import api_token
from .helpers import make_cursor, ok, param, parse_cursor, parse_since, server_time
from .serializers import article_dict, category_dict, feed_dict, tag_dict

MAX_LIMIT = 500


@api_token
@require_GET
def sync(request):
    user = request.api_user
    since = parse_since(param(request, "since"))
    cur_dt, cur_id = parse_cursor(param(request, "cursor"))
    try:
        limit = min(int(param(request, "limit", "200")), MAX_LIMIT)
    except ValueError:
        limit = 200

    from articles.models import Article

    qs = (Article.objects.filter(feed__user=user)
          .select_related("source", "feed").prefetch_related("tags")
          .order_by("updated_at", "id"))
    if since:
        qs = qs.filter(updated_at__gt=since)
    if cur_dt and cur_id:  # paginación estable por (updated_at, id)
        qs = qs.filter(Q(updated_at__gt=cur_dt) | (Q(updated_at=cur_dt) & Q(id__gt=cur_id)))

    rows = list(qs[: limit + 1])
    has_more = len(rows) > limit
    rows = rows[:limit]
    articles = [article_dict(a, user=user) for a in rows]
    next_cursor = make_cursor(rows[-1].updated_at, rows[-1].id) if (has_more and rows) else ""

    # Feeds/categorías/tags: catálogos pequeños → se mandan completos (no necesitan delta).
    from feeds.models import Category, Feed
    from articles.models import Tag

    feeds = [feed_dict(f) for f in Feed.objects.filter(user=user).select_related("source")]
    cats = [category_dict(c) for c in Category.objects.filter(user=user)]
    tags = [tag_dict(t) for t in Tag.objects.filter(user=user)]

    return ok(
        {"articles": articles, "feeds": feeds, "categories": cats, "tags": tags},
        cursor=next_cursor, has_more=has_more, server_time=server_time(),
    )
