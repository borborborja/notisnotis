from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from articles.models import Article
from features.decorators import module_required


def _episode(request, pk):
    return get_object_or_404(Article.objects.select_related("feed", "source"),
                             pk=pk, feed__user=request.user)


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
