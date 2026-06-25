"""Análisis de historias: distribución de sesgo, blindspot y resúmenes por perspectiva."""
from __future__ import annotations

from django.utils import timezone

from aiproviders.client import get_chat_client
from feeds.models import BIAS_ORDER, LEFT_BUCKETS, RIGHT_BUCKETS, Bias

SYSTEM = "Eres un editor neutral que sintetiza cobertura de múltiples medios. Devuelve solo JSON."

PROMPT = (
    "Te doy titulares de varios medios sobre el mismo suceso. Devuelve SOLO JSON:\n"
    '{{"headline": "titular neutral del suceso",\n'
    '  "neutral_summary": "resumen objetivo de 2-4 frases",\n'
    '  "perspectives": {{"left": "cómo lo enmarca la izquierda",\n'
    '                    "center": "encuadre de centro",\n'
    '                    "right": "cómo lo enmarca la derecha"}}}}\n'
    "Si falta cobertura de un lado, indícalo en esa perspectiva.\n\n"
    "COBERTURA:\n{coverage}"
)


def compute_bias_distribution(articles):
    """Cuenta artículos por bucket de sesgo de su fuente."""
    dist = {b.value: 0 for b in BIAS_ORDER}
    for art in articles:
        bias = art.source.bias
        if bias in dist:
            dist[bias] += 1
    return dist


def detect_blindspot(dist, *, dominance=0.7, starvation=0.15):
    """Marca blindspot si un lado domina la cobertura y el opuesto está infrarrepresentado.

    Devuelve (is_blindspot, side_with_blindspot) donde side es el lado que NO cubre.
    """
    total = sum(dist.values())
    if total < 3:
        return False, ""
    left = sum(dist.get(b.value, 0) for b in LEFT_BUCKETS)
    right = sum(dist.get(b.value, 0) for b in RIGHT_BUCKETS)
    if left / total >= dominance and right / total <= starvation:
        return True, "right"  # la derecha tiene el punto ciego
    if right / total >= dominance and left / total <= starvation:
        return True, "left"
    return False, ""


def _coverage_text(articles, limit=25):
    lines = []
    for art in articles[:limit]:
        bias = art.source.get_bias_display()
        snippet = (art.summary or art.body or "")[:200].replace("\n", " ")
        lines.append(f"- [{bias}] {art.source.name}: {art.title}\n  {snippet}")
    return "\n".join(lines)


def analyze_story(story, client=None):
    articles = [sa.article for sa in story.story_articles.select_related("article", "article__source")]
    if not articles:
        return story

    dist = compute_bias_distribution(articles)
    is_blind, side = detect_blindspot(dist)

    # La síntesis LLM (resumen neutral + perspectivas) solo tiene sentido con VARIAS
    # fuentes. Las historias de una sola fuente se procesan sin LLM (ahorra coste): se
    # quedan con su titular y la barra de sesgo.
    n_sources = len({a.source_id for a in articles})
    data = {}
    if n_sources >= 2:
        client = client or get_chat_client()
        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": PROMPT.format(coverage=_coverage_text(articles))},
        ]
        try:
            data = client.chat(messages, json=True)
        except Exception:
            data = {}

    persp = data.get("perspectives") or {}
    story.headline = (data.get("headline") or story.headline or articles[0].title)[:500]
    story.neutral_summary = data.get("neutral_summary") or ""
    story.perspectives = {
        "left": persp.get("left", ""),
        "center": persp.get("center", ""),
        "right": persp.get("right", ""),
    }
    story.bias_distribution = dist
    story.is_blindspot = is_blind
    story.blindspot_side = side
    story.analyzed_at = timezone.now()
    story.dirty = False

    # Notificación push al detectar un blindspot por primera vez.
    notify = is_blind and not story.blindspot_notified
    if notify:
        story.blindspot_notified = True
    elif not is_blind:
        story.blindspot_notified = False
    story.save()

    if notify:
        try:
            from notifications.push import send_push

            send_push(story.user, "Nuevo blindspot", story.headline, url=f"/story/{story.pk}/")
        except Exception:  # noqa: BLE001
            pass
    return story
