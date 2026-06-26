from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from features.decorators import feature_required

from .models import AIFeed, AIFeedCandidate


@login_required
@feature_required("aifeeds")
def feed_list(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()[:200]
        description = request.POST.get("description", "").strip()
        if name and description:
            from .services import ensure_feed

            cfg = getattr(request.user, "config", None)
            min_score = int((cfg.data.get("ai_min_score", 6) if cfg else 6))
            ai = AIFeed.objects.create(user=request.user, name=name, description=description,
                                       min_score=min_score)
            ensure_feed(ai)  # crea el feed sintético ya (aparece en el sidebar)
            messages.success(request, "Feed con IA creado. Pulsa “Buscar ahora” para ver propuestas.")
        return redirect("aifeeds:list")
    feeds = AIFeed.objects.filter(user=request.user).annotate(
        n_pending=Count("candidates", filter=Q(candidates__status=AIFeedCandidate.PENDING)),
        n_accepted=Count("candidates", filter=Q(candidates__status=AIFeedCandidate.ACCEPTED)),
    )
    return render(request, "aifeeds/list.html", {"feeds": feeds})


@login_required
@feature_required("aifeeds")
def feed_detail(request, pk):
    ai = get_object_or_404(AIFeed, pk=pk, user=request.user)
    pending = ai.candidates.filter(status=AIFeedCandidate.PENDING)
    accepted = ai.candidates.filter(status=AIFeedCandidate.ACCEPTED).select_related("article")[:30]
    return render(request, "aifeeds/detail.html",
                  {"ai": ai, "pending": pending, "accepted": accepted})


@login_required
@require_POST
@feature_required("aifeeds")
def search_now(request, pk):
    ai = get_object_or_404(AIFeed, pk=pk, user=request.user)
    from .services import run_search

    try:
        n = run_search(ai)
        messages.success(request, f"{n} propuestas nuevas." if n else "Sin propuestas nuevas por ahora.")
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f"No se pudo buscar: {exc}")
    return redirect("aifeeds:detail", pk=ai.pk)


@login_required
@require_POST
@feature_required("aifeeds")
def candidate_decide(request, pk):
    """Marca una propuesta como Encaja (crea artículo) o No encaja (ejemplo negativo)."""
    cand = get_object_or_404(AIFeedCandidate, pk=pk, ai_feed__user=request.user,
                             status=AIFeedCandidate.PENDING)
    from .services import accept_candidate, reject_candidate

    if request.POST.get("decision") == "accept":
        accept_candidate(cand)
    else:
        reject_candidate(cand)
    # htmx: devuelve vacío para que la tarjeta desaparezca.
    from django.http import HttpResponse

    return HttpResponse("")


@login_required
@require_POST
@feature_required("aifeeds")
def feed_delete(request, pk):
    get_object_or_404(AIFeed, pk=pk, user=request.user).delete()
    messages.success(request, "Feed con IA eliminado.")
    return redirect("aifeeds:list")
