"""Modo inteligente: estima la cadencia de actualización según la frecuencia de publicación."""
from __future__ import annotations

from statistics import median

# Límites: no consultar más de cada 15 min ni menos de una vez al día.
MIN_MINUTES = 15
MAX_MINUTES = 24 * 60


def compute_interval_minutes(feed, sample=20):
    """Mediana del hueco entre publicaciones recientes, en minutos. None si no hay datos."""
    times = list(
        feed.articles.exclude(published_at__isnull=True)
        .order_by("-published_at")
        .values_list("published_at", flat=True)[:sample]
    )
    if len(times) < 4:
        return None
    gaps = [(times[i - 1] - times[i]).total_seconds() / 60 for i in range(1, len(times))]
    gaps = [g for g in gaps if g > 0]
    if not gaps:
        return None
    return max(MIN_MINUTES, min(MAX_MINUTES, int(median(gaps))))


def update_auto_intervals(feeds):
    """Recalcula fetch_interval_minutes para los feeds en modo inteligente. Devuelve nº actualizados."""
    updated = 0
    for feed in feeds:
        if not feed.auto_interval:
            continue
        minutes = compute_interval_minutes(feed)
        if minutes and minutes != feed.fetch_interval_minutes:
            feed.fetch_interval_minutes = minutes
            feed.save(update_fields=["fetch_interval_minutes"])
            updated += 1
    return updated
