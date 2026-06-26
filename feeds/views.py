from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.management import call_command
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .discovery import discover_feeds, feed_title
from .models import Category, Feed, Rule, Source
from .opml import _domain, crawl_new_feeds, import_opml_for_user


def _create_feed(user, url, title, category=None, kind=None):
    domain = _domain(url) or "unknown"
    source, _ = Source.objects.get_or_create(domain=domain, defaults={"name": title or domain})
    if not kind:
        kind = "youtube" if "youtube.com/feeds/videos.xml" in url else "rss"
    feed, created = Feed.objects.get_or_create(
        user=user, url=url,
        defaults={"source": source, "title": title or "", "category": category, "kind": kind,
                  "crawler": crawl_new_feeds(user)},
    )
    return feed, created


@login_required
def feed_list(request):
    from django.db.models import Count, Q

    from aifeeds.models import AIFeed, AIFeedCandidate

    feeds = (Feed.objects.filter(user=request.user, ai_feed__isnull=True)
             .select_related("source", "category").order_by("title"))
    categories = Category.objects.filter(user=request.user)
    ai_feeds = AIFeed.objects.filter(user=request.user).annotate(
        n_pending=Count("candidates", filter=Q(candidates__status=AIFeedCandidate.PENDING)),
        n_accepted=Count("candidates", filter=Q(candidates__status=AIFeedCandidate.ACCEPTED)),
    )
    active = request.GET.get("tab", "rss")
    if active not in ("rss", "ia", "podcasts"):
        active = "rss"
    return render(request, "feeds/feed_list.html", {
        "feeds": feeds,
        "rss_feeds": [f for f in feeds if f.kind == "rss"],
        "podcast_feeds": [f for f in feeds if f.kind in ("podcast", "youtube")],
        "ai_feeds": ai_feeds,
        "categories": categories,
        "active": active,
    })


@login_required
def podcast_search(request):
    """Buscador de podcasts (htmx): devuelve resultados del directorio para suscribirse."""
    from .podcastsearch import search_podcasts

    q = request.GET.get("q", "").strip()
    results, error = [], ""
    if q:
        try:
            results = search_podcasts(q)
        except Exception as exc:  # noqa: BLE001
            error = str(exc)[:200]
    return render(request, "feeds/_podcast_results.html", {"results": results, "error": error, "q": q})


@login_required
def upload_opml(request):
    if request.method == "POST":
        f = request.FILES.get("opml")
        if not f:
            messages.error(request, "Selecciona un archivo OPML.")
            return redirect("feeds:upload_opml")
        kind = request.POST.get("kind", "rss")
        if kind not in ("rss", "podcast"):
            kind = "rss"
        try:
            content = f.read()
            created, skipped = import_opml_for_user(request.user, content, kind=kind)
        except Exception as exc:  # noqa: BLE001 - feedback al usuario
            messages.error(request, f"No se pudo importar el OPML: {exc}")
            return redirect("feeds:upload_opml")
        messages.success(
            request,
            f"OPML importado: {created} feeds nuevos, {skipped} ya existían.",
        )
        return redirect(f"{reverse('feeds:feed_list')}?tab={'podcasts' if kind == 'podcast' else 'rss'}")
    return render(request, "feeds/upload_opml.html", {"kind": request.GET.get("kind", "rss")})


@login_required
def export_opml(request):
    """Exporta los feeds del usuario como OPML, agrupados por categoría."""
    from xml.sax.saxutils import quoteattr

    feeds = Feed.objects.filter(user=request.user).select_related("source", "category")
    by_cat = {}
    for f in feeds:
        by_cat.setdefault(f.category.name if f.category else None, []).append(f)

    def outline(f):
        title = quoteattr(f.title or f.source.name)
        return f'      <outline text={title} title={title} type="rss" xmlUrl={quoteattr(f.url)} htmlUrl={quoteattr("https://" + f.source.domain)}/>'

    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<opml version="2.0">',
             "  <head><title>NotisNotis</title></head>", "  <body>"]
    for cat, items in sorted(by_cat.items(), key=lambda kv: (kv[0] is None, kv[0] or "")):
        if cat:
            lines.append(f"    <outline text={quoteattr(cat)} title={quoteattr(cat)}>")
            lines += [outline(f) for f in items]
            lines.append("    </outline>")
        else:
            lines += ["    " + outline(f).strip() for f in items]
    lines += ["  </body>", "</opml>"]

    resp = HttpResponse("\n".join(lines), content_type="text/x-opml; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="notisnotis.opml"'
    return resp


@login_required
@require_POST
def refresh(request):
    """Refresca feeds ahora. Con feed/categoría seleccionada fuerza; sin scope, solo los vencidos."""
    feed = request.POST.get("feed")
    category = request.POST.get("category")
    kwargs = {"user": request.user.username}
    if feed:
        kwargs["feed"] = int(feed)
        kwargs["force"] = True
    elif category and category != "none":
        kwargs["category"] = int(category)
        kwargs["force"] = True
    try:
        call_command("fetch_feeds", **kwargs)
        messages.success(request, "Feeds actualizados.")
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f"No se pudo refrescar: {exc}")
    return redirect(request.POST.get("next") or "articles:list")


@login_required
def rule_list(request):
    if request.method == "POST":
        from articles.models import Tag

        name = request.POST.get("name", "").strip()[:200]
        if name:
            tag = None
            tag_name = request.POST.get("action_tag", "").strip()
            if tag_name:
                tag, _ = Tag.objects.get_or_create(user=request.user, name=tag_name[:100])
            Rule.objects.create(
                user=request.user, name=name,
                pattern=request.POST.get("pattern", "").strip()[:300],
                match_in=request.POST.get("match_in", "any"),
                feed=Feed.objects.filter(id=request.POST.get("feed") or 0, user=request.user).first(),
                category=Category.objects.filter(id=request.POST.get("category") or 0, user=request.user).first(),
                action_mark_read=request.POST.get("action_mark_read") == "1",
                action_star=request.POST.get("action_star") == "1",
                action_tag=tag,
            )
            messages.success(request, "Regla creada.")
        return redirect("feeds:rule_list")
    return render(request, "feeds/rules.html", {
        "rules": request.user.rules.select_related("feed", "category", "action_tag"),
        "feeds": Feed.objects.filter(user=request.user).select_related("source"),
        "categories": Category.objects.filter(user=request.user),
    })


@login_required
@require_POST
def rule_delete(request, pk):
    get_object_or_404(Rule, pk=pk, user=request.user).delete()
    return redirect("feeds:rule_list")


@login_required
@require_POST
def rule_toggle(request, pk):
    rule = get_object_or_404(Rule, pk=pk, user=request.user)
    rule.enabled = not rule.enabled
    rule.save(update_fields=["enabled"])
    return redirect("feeds:rule_list")


@login_required
def subscribe(request):
    categories = Category.objects.filter(user=request.user)
    kind = request.POST.get("kind") if request.method == "POST" else request.GET.get("kind")
    kind = kind if kind in ("rss", "podcast") else None
    dest = redirect(f"{reverse('feeds:feed_list')}?tab={'podcasts' if kind == 'podcast' else 'rss'}")
    if request.method == "POST":
        cat = categories.filter(id=request.POST.get("category")).first()
        direct = request.POST.get("feed_url")
        if direct:  # el usuario eligió un candidato
            _, created = _create_feed(request.user, direct,
                                      request.POST.get("title") or feed_title(direct), cat, kind=kind)
            messages.success(request, "Feed añadido." if created else "Ese feed ya existía.")
            return dest
        url = request.POST.get("url", "").strip()
        candidates = discover_feeds(url) if url else []
        if not candidates:
            messages.error(request, "No se encontró ningún feed en esa URL.")
        elif len(candidates) == 1:
            _, created = _create_feed(request.user, candidates[0][0], candidates[0][1], cat, kind=kind)
            messages.success(request, "Feed añadido." if created else "Ese feed ya existía.")
            return dest
        else:
            return render(request, "feeds/subscribe.html",
                          {"candidates": candidates, "categories": categories, "url": url,
                           "category": cat, "kind": kind})
    return render(request, "feeds/subscribe.html", {"categories": categories, "kind": kind})


@login_required
@require_POST
def category_create(request):
    name = request.POST.get("name", "").strip()[:200]
    if name:
        Category.objects.get_or_create(user=request.user, name=name)
    return redirect(request.POST.get("next") or "feeds:feed_list")


@login_required
@require_POST
def category_rename(request, pk):
    cat = get_object_or_404(Category, pk=pk, user=request.user)
    name = request.POST.get("name", "").strip()[:200]
    if name:
        cat.name = name
        cat.save(update_fields=["name"])
    return redirect("feeds:feed_list")


@login_required
@require_POST
def category_delete(request, pk):
    get_object_or_404(Category, pk=pk, user=request.user).delete()  # feeds → SET_NULL
    messages.success(request, "Categoría eliminada (sus feeds quedan sin categoría).")
    return redirect("feeds:feed_list")


@login_required
@require_POST
def category_reorder(request):
    for pos, cid in enumerate(request.POST.get("order", "").split(",")):
        if cid.isdigit():
            Category.objects.filter(pk=cid, user=request.user).update(position=pos)
    return HttpResponse(status=204)


@login_required
@require_POST
def feed_set_category(request, pk):
    feed = get_object_or_404(Feed, pk=pk, user=request.user)
    cid = request.POST.get("category")
    feed.category = Category.objects.filter(pk=cid, user=request.user).first() if cid else None
    feed.save(update_fields=["category"])
    return HttpResponse(status=204)


@login_required
@require_POST
def reactivate_feed(request, pk):
    feed = get_object_or_404(Feed, pk=pk, user=request.user)
    feed.enabled = True
    feed.fail_count = 0
    feed.last_error = ""
    feed.save(update_fields=["enabled", "fail_count", "last_error"])
    messages.success(request, "Feed reactivado.")
    return redirect("feeds:feed_list")


@login_required
def feed_edit(request, pk):
    feed = get_object_or_404(Feed.objects.select_related("source"), pk=pk, user=request.user)
    categories = Category.objects.filter(user=request.user)
    if request.method == "POST":
        feed.title = request.POST.get("title", "").strip()[:500]
        cat_id = request.POST.get("category")
        feed.category = categories.filter(id=cat_id).first() if cat_id else None
        feed.enabled = request.POST.get("enabled") == "1"
        feed.crawler = request.POST.get("crawler") == "1"
        feed.auto_interval = request.POST.get("auto_interval") == "1"
        kind = request.POST.get("kind", feed.kind)
        if kind in dict(Feed.KIND_CHOICES):
            feed.kind = kind
        try:
            feed.fetch_interval_minutes = max(5, int(request.POST.get("interval", feed.fetch_interval_minutes)))
        except (TypeError, ValueError):
            pass
        feed.save()
        messages.success(request, "Feed actualizado.")
        return redirect("feeds:feed_list")
    return render(request, "feeds/feed_edit.html", {"feed": feed, "categories": categories})


@login_required
def toggle_feed(request, pk):
    feed = get_object_or_404(Feed, pk=pk, user=request.user)
    feed.enabled = not feed.enabled
    feed.save(update_fields=["enabled"])
    return redirect("feeds:feed_list")


@login_required
def delete_feed(request, pk):
    feed = get_object_or_404(Feed, pk=pk, user=request.user)
    if request.method == "POST":
        feed.delete()
        messages.success(request, "Feed eliminado.")
    return redirect("feeds:feed_list")
