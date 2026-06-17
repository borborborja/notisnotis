from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from articles.models import Article
from feeds.models import BIAS_ORDER, LEFT_BUCKETS, RIGHT_BUCKETS, Source

from .models import Story


@login_required
def home(request):
    qs = Story.objects.filter(user=request.user).prefetch_related("story_articles")
    flt = request.GET.get("filter", "")
    title = "Historias"
    if flt == "blindspot":
        qs = qs.filter(is_blindspot=True)
        title = "⚠ Blindspots"
    bucket = request.GET.get("bias")
    if bucket:
        qs = [s for s in qs if s.bias_distribution.get(bucket, 0) > 0]

    page = Paginator(list(qs), 20).get_page(request.GET.get("page"))
    for story in page:
        story.bars = _bias_bars(story.bias_distribution)
    return render(request, "stories/home.html", {"page": page, "filter": flt, "bucket": bucket, "list_title": title})


@login_required
def topic_list(request):
    from .models import Topic

    if request.method == "POST":
        name = request.POST.get("name", "").strip()[:200]
        keywords = request.POST.get("keywords", "").strip()[:500]
        if name and keywords:
            Topic.objects.create(user=request.user, name=name, keywords=keywords,
                                 notify=request.POST.get("notify") == "1")
        return redirect("stories:topic_list")
    return render(request, "stories/topics.html", {"topics": request.user.topics.all()})


@login_required
@require_POST
def topic_delete(request, pk):
    from .models import Topic

    get_object_or_404(Topic, pk=pk, user=request.user).delete()
    return redirect("stories:topic_list")


@login_required
def trending(request):
    """Historias más cubiertas ahora (por nº de fuentes y recencia)."""
    since = timezone.now() - timedelta(days=3)
    stories = list(
        Story.objects.filter(user=request.user, last_updated__gte=since)
        .annotate(n=Count("story_articles")).order_by("-n", "-last_updated")[:30]
    )
    for s in stories:
        s.bars = _bias_bars(s.bias_distribution)
    return render(request, "stories/trending.html", {"page": stories, "list_title": "Tendencias"})


@login_required
def compare_sources(request):
    """Compara la cobertura de dos fuentes: exclusivas de cada una y comunes."""
    sources = Source.objects.filter(feeds__user=request.user).distinct()
    a, b = request.GET.get("a"), request.GET.get("b")
    result = None
    if a and b and a != b:
        from .models import StoryArticle

        def story_ids(src):
            return set(StoryArticle.objects.filter(story__user=request.user, article__source_id=src)
                       .values_list("story_id", flat=True))
        sa, sb = story_ids(a), story_ids(b)
        both, only_a, only_b = sa & sb, sa - sb, sb - sa
        result = {
            "both": Story.objects.filter(id__in=both)[:40],
            "only_a": Story.objects.filter(id__in=only_a)[:40],
            "only_b": Story.objects.filter(id__in=only_b)[:40],
            "source_a": Source.objects.filter(id=a).first(),
            "source_b": Source.objects.filter(id=b).first(),
        }
    return render(request, "stories/compare.html", {"sources": sources, "a": a, "b": b, "result": result})


def _story_context(request, pk):
    story = get_object_or_404(Story, pk=pk, user=request.user)
    sas = story.story_articles.select_related("article", "article__source").order_by(
        "-article__published_at"
    )
    grouped = {b.value: {"label": b.label, "articles": []} for b in BIAS_ORDER}
    grouped["unknown"] = {"label": "Desconocido", "articles": []}
    for sa in sas:
        bucket = sa.article.source.bias
        grouped.setdefault(bucket, {"label": bucket, "articles": []})["articles"].append(sa.article)
    grouped = {k: v for k, v in grouped.items() if v["articles"]}
    return {"story": story, "grouped": grouped, "bars": _bias_bars(story.bias_distribution)}


@login_required
def story_reading(request, pk):
    """Panel de lectura de una historia (parcial htmx)."""
    return render(request, "stories/_story_reading.html", _story_context(request, pk))


@login_required
def story_detail(request, pk):
    return render(request, "stories/story_detail.html", _story_context(request, pk))


@login_required
def bias_diet(request):
    """Dieta informativa: sesgo de lo que el usuario realmente LEE."""
    try:
        days = max(1, min(365, int(request.GET.get("days", 30))))
    except ValueError:
        days = 30
    since = timezone.now() - timedelta(days=days)
    dist = {b.value: 0 for b in BIAS_ORDER}
    rows = Article.objects.filter(
        feed__user=request.user, is_read=True, read_at__gte=since
    ).values_list("source__bias", flat=True)
    for b in rows:
        if b in dist:
            dist[b] += 1
    total = sum(dist.values())
    left = sum(dist[b.value] for b in LEFT_BUCKETS)
    right = sum(dist[b.value] for b in RIGHT_BUCKETS)
    msg = "Sin artículos leídos en este periodo."
    if total:
        lp, rp = round(100 * left / total), round(100 * right / total)
        if lp >= 60:
            msg = f"Lees sobre todo medios de izquierda ({lp}%). Prueba a equilibrar."
        elif rp >= 60:
            msg = f"Lees sobre todo medios de derecha ({rp}%). Prueba a equilibrar."
        else:
            msg = "Tu dieta informativa está razonablemente equilibrada."
    return render(request, "stories/bias_diet.html", {
        "bars": _bias_bars(dist), "total": total, "days": days, "message": msg,
    })


def _bias_bars(dist):
    """Devuelve lista de (bucket, label, pct) para la barra de sesgo."""
    total = sum(dist.values()) or 1
    bars = []
    for b in BIAS_ORDER:
        count = dist.get(b.value, 0)
        bars.append({"bucket": b.value, "label": b.label, "count": count, "pct": round(100 * count / total)})
    return bars
