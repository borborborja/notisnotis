from django import template

register = template.Library()


@register.filter
def duration_hm(seconds):
    """Segundos → '1h 23min' o '12 min' o '0:45'."""
    try:
        s = int(seconds or 0)
    except (TypeError, ValueError):
        return ""
    if s <= 0:
        return ""
    h, m = s // 3600, (s % 3600) // 60
    if h:
        return f"{h}h {m}min"
    if m:
        return f"{m} min"
    return f"0:{s:02d}"
