from .modules import enabled_modules
from .registry import enabled_features


def features(request):
    """Expone `features` (set de keys activas) y `feature_tiers` a las plantillas."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"features": set()}
    return {"features": enabled_features(user)}


def modules(request):
    """Expone `modules` (set de sectores activos: rss/curation/podcasts) a las plantillas."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"modules": {"rss"}}
    return {"modules": enabled_modules(user)}
