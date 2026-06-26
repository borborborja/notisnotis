"""API de podcasts: podcasts, episodios, cola Up Next, progreso/escuchado y ajustes."""
from __future__ import annotations

from django.db.models import Count, Q
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from .auth import api_token
from .helpers import body_json, err, ok, param, require_module
from .serializers import episode_dict, feed_dict, queue_dict

MODULE = "podcasts"


def _guard(request):
    return require_module(request.api_user, MODULE)


@api_token
@require_GET
def podcasts(request):
    if (g := _guard(request)):
        return g
    from feeds.models import Feed

    qs = (Feed.objects.filter(user=request.api_user, kind="podcast").select_related("source")
          .annotate(n_episodes=Count("articles"),
                    n_unplayed=Count("articles", filter=Q(articles__is_read=False))))
    out = []
    for f in qs:
        d = feed_dict(f)
        d["n_episodes"] = f.n_episodes
        d["n_unplayed"] = f.n_unplayed
        out.append(d)
    return ok(out)


@api_token
@require_GET
def podcast_detail(request, pk):
    if (g := _guard(request)):
        return g
    from feeds.models import Feed

    f = Feed.objects.filter(user=request.api_user, kind="podcast", pk=pk).select_related("source").first()
    if not f:
        return err("not_found", "Podcast no encontrado.", status=404)
    eps = (f.articles.select_related("source").order_by("-published_at", "-id")[:100])
    d = feed_dict(f)
    d["episodes"] = [episode_dict(a, user=request.api_user) for a in eps]
    return ok(d)


@api_token
@require_GET
def episodes(request):
    if (g := _guard(request)):
        return g
    from articles.models import Article

    qs = (Article.objects.filter(feed__user=request.api_user, feed__kind="podcast")
          .select_related("source", "feed").order_by("-published_at", "-id"))
    if param(request, "feed"):
        qs = qs.filter(feed_id=param(request, "feed"))
    if param(request, "in_progress") == "1":
        qs = qs.filter(play_position__gt=0, is_read=False)
    try:
        limit = min(int(param(request, "limit", "50")), 200)
    except ValueError:
        limit = 50
    return ok([episode_dict(a, user=request.api_user) for a in qs[:limit]])


# --- cola Up Next ---
@api_token
@require_http_methods(["GET", "POST"])
def queue(request):
    if (g := _guard(request)):
        return g
    from podcasts.models import QueueItem
    from articles.models import Article

    if request.method == "GET":
        items = (QueueItem.objects.filter(user=request.api_user)
                 .select_related("article", "article__source").order_by("position", "added_at"))
        return ok([queue_dict(q) for q in items])
    # POST {episode_id, position?}
    data = body_json(request)
    ep = Article.objects.filter(feed__user=request.api_user, pk=data.get("episode_id")).first()
    if not ep:
        return err("not_found", "Episodio no encontrado.", status=404)
    pos = data.get("position")
    if pos is None:
        pos = (QueueItem.objects.filter(user=request.api_user).count())
    q, _ = QueueItem.objects.get_or_create(user=request.api_user, article=ep,
                                           defaults={"position": pos})
    return ok(queue_dict(q))


@api_token
@require_http_methods(["DELETE"])
def queue_remove(request, pk):
    if (g := _guard(request)):
        return g
    from podcasts.models import QueueItem

    QueueItem.objects.filter(user=request.api_user, article_id=pk).delete()
    return ok({"removed": pk})


@api_token
@require_http_methods(["POST"])
def queue_reorder(request):
    if (g := _guard(request)):
        return g
    from podcasts.models import QueueItem

    ids = body_json(request).get("ids", [])
    for i, ep_id in enumerate(ids):
        QueueItem.objects.filter(user=request.api_user, article_id=ep_id).update(position=i)
    return ok({"ok": True})


# --- reproducción ---
def _episode(request, pk):
    from articles.models import Article

    return Article.objects.filter(feed__user=request.api_user, pk=pk).first()


@api_token
@require_http_methods(["POST"])
def progress(request, pk):
    if (g := _guard(request)):
        return g
    ep = _episode(request, pk)
    if not ep:
        return err("not_found", "Episodio no encontrado.", status=404)
    data = body_json(request)
    ep.play_position = int(data.get("position", ep.play_position) or 0)
    if data.get("duration"):
        ep.duration = int(data["duration"])
    ep.play_updated_at = timezone.now()
    ep.save(update_fields=["play_position", "duration", "play_updated_at"])
    return ok(episode_dict(ep, user=request.api_user))


@api_token
@require_http_methods(["POST"])
def played(request, pk):
    if (g := _guard(request)):
        return g
    ep = _episode(request, pk)
    if not ep:
        return err("not_found", "Episodio no encontrado.", status=404)
    ep.is_read = True
    ep.read_at = timezone.now()
    ep.play_position = 0
    ep.play_updated_at = timezone.now()
    ep.save(update_fields=["is_read", "read_at", "play_position", "play_updated_at"])
    from podcasts.models import QueueItem

    QueueItem.objects.filter(user=request.api_user, article=ep).delete()
    return ok(episode_dict(ep, user=request.api_user))


@api_token
@require_http_methods(["PATCH", "POST"])
def podcast_settings(request, pk):
    if (g := _guard(request)):
        return g
    from feeds.models import Feed

    f = Feed.objects.filter(user=request.api_user, kind="podcast", pk=pk).first()
    if not f:
        return err("not_found", "Podcast no encontrado.", status=404)
    data = body_json(request)
    fields = []
    for key, cast in (("playback_speed", float), ("skip_intro", int), ("skip_outro", int)):
        if key in data:
            setattr(f, key, cast(data[key]))
            fields.append(key)
    if fields:
        f.save(update_fields=fields)
    return ok(feed_dict(f))
