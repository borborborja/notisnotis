from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from articles.models import Article
from feeds.models import Feed
from features.decorators import module_required

from .models import QueueItem


def _episode(request, pk):
    return get_object_or_404(Article.objects.select_related("feed", "source"),
                             pk=pk, feed__user=request.user)


def _episodes(request):
    """Episodios de podcasts del usuario (audio)."""
    return (Article.objects.filter(feed__user=request.user, feed__kind__in=["podcast", "youtube"])
            .select_related("feed", "source"))


# ---------------- Vistas (Pocket Casts) ----------------

@login_required
@module_required("podcasts")
def home(request):
    """Grid de podcasts suscritos + accesos a cola/en curso/favoritos."""
    feeds = (Feed.objects.filter(user=request.user, kind__in=["podcast", "youtube"])
             .select_related("source")
             .annotate(unplayed=Count("articles", filter=Q(articles__is_read=False)))
             .order_by("title"))
    queue_n = QueueItem.objects.filter(user=request.user).count()
    in_progress_qs = _episodes(request).filter(play_position__gt=0, is_read=False).order_by("-play_updated_at")
    in_progress = list(in_progress_qs[:10])
    return render(request, "podcasts/home.html", {
        "feeds": feeds, "queue_n": queue_n, "in_progress": in_progress,
        "in_progress_n": in_progress_qs.count(), "active": "podcasts",
    })


@login_required
@module_required("podcasts")
def podcast_detail(request, pk):
    feed = get_object_or_404(Feed.objects.select_related("source"), pk=pk, user=request.user)
    episodes = feed.articles.select_related("feed", "source").order_by("-published_at")[:200]
    queued = set(QueueItem.objects.filter(user=request.user).values_list("article_id", flat=True))
    return render(request, "podcasts/detail.html", {
        "feed": feed, "episodes": episodes, "queued": queued, "active": "podcasts",
        "n_episodes": feed.articles.count(),
        "n_unplayed": feed.articles.filter(is_read=False).count(),
    })


@login_required
@module_required("podcasts")
def filtered(request, kind):
    """Listas: en curso / nuevos / favoritos."""
    qs = _episodes(request)
    if kind == "in_progress":
        qs = qs.filter(play_position__gt=0, is_read=False).order_by("-play_updated_at")
        title = "En curso"
    elif kind == "favorites":
        qs = qs.filter(is_saved=True).order_by("-published_at")
        title = "Favoritos"
    else:
        qs = qs.filter(is_read=False).order_by("-published_at")
        title = "Nuevos episodios"
    queued = set(QueueItem.objects.filter(user=request.user).values_list("article_id", flat=True))
    episodes = list(qs[:200])
    return render(request, "podcasts/list.html", {
        "title": title, "episodes": episodes, "n": qs.count(), "queued": queued, "active": "podcasts",
    })


@login_required
@module_required("podcasts")
def downloads(request):
    """Página de descargas offline (se rellena en cliente desde localStorage)."""
    return render(request, "podcasts/downloads.html", {"active": "podcasts"})


@login_required
@module_required("podcasts")
def up_next(request):
    items = (QueueItem.objects.filter(user=request.user)
             .select_related("article", "article__feed", "article__source"))
    return render(request, "podcasts/up_next.html", {
        "items": items, "active": "podcasts",
    })


# ---------------- Acciones por podcast ----------------

@login_required
@module_required("podcasts")
@require_POST
def mark_feed_played(request, pk):
    """Marca todos los episodios de un podcast como escuchados."""
    from django.contrib import messages
    from django.utils import timezone

    feed = get_object_or_404(Feed, pk=pk, user=request.user)
    now = timezone.now()
    n = feed.articles.filter(is_read=False).update(is_read=True, read_at=now, updated_at=now)
    messages.success(request, f"{n} episodio{'s' if n != 1 else ''} marcados como escuchados.")
    return redirect("podcasts:detail", pk=pk)


# ---------------- Cola ----------------

@login_required
@module_required("podcasts")
@require_POST
def queue_clear(request):
    QueueItem.objects.filter(user=request.user).delete()
    return redirect("podcasts:up_next")


@login_required
@module_required("podcasts")
@require_POST
def queue_add(request, pk):
    ep = _episode(request, pk)
    last = QueueItem.objects.filter(user=request.user).order_by("-position").first()
    pos = (last.position + 1) if last else 0
    QueueItem.objects.get_or_create(user=request.user, article=ep, defaults={"position": pos})
    return JsonResponse({"ok": True, "queued": True})


@login_required
@module_required("podcasts")
@require_POST
def queue_remove(request, pk):
    QueueItem.objects.filter(user=request.user, article_id=pk).delete()
    if request.headers.get("X-Requested-With") == "fetch":
        return JsonResponse({"ok": True, "queued": False})
    return redirect("podcasts:up_next")


@login_required
@module_required("podcasts")
@require_POST
def import_antennapod(request):
    """Sube un backup .db de AntennaPod y lo importa (streamea a disco temporal)."""
    import os
    import tempfile

    from .antennapod import import_backup

    upload = request.FILES.get("db")
    if not upload:
        from django.contrib import messages
        messages.error(request, "Selecciona el fichero .db de AntennaPod.")
        return redirect("podcasts:home")

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    try:
        for chunk in upload.chunks():
            tmp.write(chunk)
        tmp.close()
        counts = import_backup(request.user, tmp.name)
    except Exception as exc:  # noqa: BLE001 - feedback al usuario
        from django.contrib import messages
        messages.error(request, f"No se pudo importar el backup: {exc}")
        return redirect("podcasts:home")
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
    from django.contrib import messages
    messages.success(request, "Backup AntennaPod importado: " + ", ".join(
        f"{v} {k}" for k, v in counts.items() if v))
    return redirect("podcasts:home")


@login_required
@module_required("podcasts")
@require_POST
def queue_reorder(request):
    order = request.POST.getlist("order[]") or request.POST.getlist("order")
    items = {str(qi.article_id): qi
             for qi in QueueItem.objects.filter(user=request.user)}
    for i, aid in enumerate(order):
        qi = items.get(str(aid))
        if qi and qi.position != i:
            qi.position = i
            qi.save(update_fields=["position"])
    return JsonResponse({"ok": True})


@login_required
@module_required("podcasts")
@require_POST
def progress(request, pk):
    """Guarda la posición de reproducción (se llama cada ~15s y por sendBeacon)."""
    ep = _episode(request, pk)
    try:
        pos = max(0, int(float(request.POST.get("position", 0))))
    except (TypeError, ValueError):
        pos = 0
    try:
        dur = max(0, int(float(request.POST.get("duration", 0))))
    except (TypeError, ValueError):
        dur = 0
    ep.play_position = pos
    fields = ["play_position", "play_updated_at"]
    if dur:
        ep.duration = dur
        fields.append("duration")
    # Cerca del final → escuchado.
    if dur and pos >= dur - 30 and not ep.is_read:
        ep.is_read = True
        ep.read_at = timezone.now()
        ep.play_position = 0
        fields += ["is_read", "read_at"]
    ep.play_updated_at = timezone.now()
    ep.save(update_fields=fields)
    return JsonResponse({"ok": True, "played": ep.is_read})


@login_required
@module_required("podcasts")
@require_POST
def played(request, pk):
    """Marca/desmarca un episodio como escuchado (resetea posición al marcar)."""
    ep = _episode(request, pk)
    ep.is_read = not ep.is_read
    ep.read_at = timezone.now() if ep.is_read else None
    if ep.is_read:
        ep.play_position = 0
    ep.play_updated_at = timezone.now()
    ep.save(update_fields=["is_read", "read_at", "play_position", "play_updated_at"])
    return JsonResponse({"ok": True, "played": ep.is_read})
