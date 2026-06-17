from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from feeds.models import BIAS_ORDER

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


def _bias_bars(dist):
    """Devuelve lista de (bucket, label, pct) para la barra de sesgo."""
    total = sum(dist.values()) or 1
    bars = []
    for b in BIAS_ORDER:
        count = dist.get(b.value, 0)
        bars.append({"bucket": b.value, "label": b.label, "count": count, "pct": round(100 * count / total)})
    return bars
