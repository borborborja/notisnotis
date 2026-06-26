"""Tendencias globales: titulares de Google News por país + usuarios de sistema que poseen
las historias de tendencia (para reutilizar el pipeline de agregación tal cual).
"""
from __future__ import annotations

import feedparser

from notisnotis import optconfig

# (code, label, gnews_hl, gnews_gl, searx_lang)
COUNTRIES = [
    ("ES", "España", "es", "ES", "es"),
    ("MX", "México", "es-419", "MX", "es"),
    ("AR", "Argentina", "es-419", "AR", "es"),
    ("US", "Estados Unidos", "en-US", "US", "en"),
    ("GB", "Reino Unido", "en-GB", "GB", "en"),
    ("FR", "Francia", "fr", "FR", "fr"),
    ("DE", "Alemania", "de", "DE", "de"),
    ("IT", "Italia", "it", "IT", "it"),
    ("PT", "Portugal", "pt-PT", "PT", "pt"),
    ("BR", "Brasil", "pt-BR", "BR", "pt"),
]
_BY_CODE = {c[0]: c for c in COUNTRIES}
DEFAULT_COUNTRY = "ES"

# Field de cascada para el país (operador en .env > usuario > default).
COUNTRY_FIELD = ("trending_country", "TRENDING_COUNTRY", DEFAULT_COUNTRY, "str", False,
                 "País de tendencias", [c[0] for c in COUNTRIES])


def country_meta(code):
    return _BY_CODE.get((code or "").upper(), _BY_CODE[DEFAULT_COUNTRY])


def resolve_country(user):
    code = optconfig.resolve([COUNTRY_FIELD], user)["trending_country"].upper()
    return code if code in _BY_CODE else DEFAULT_COUNTRY


def country_locked():
    return optconfig.is_locked(COUNTRY_FIELD)


def _clean_title(title):
    # Google News añade " - Fuente" al final; lo quitamos para buscar mejor.
    if " - " in title:
        head, _, tail = title.rpartition(" - ")
        if head and len(tail) < 40:
            return head.strip()
    return title.strip()


def top_headlines(country, limit=20, timeout=20):
    """Titulares en tendencia (top stories) de Google News para un país."""
    _, _, hl, gl, _ = country_meta(country)
    ceid = f"{gl}:{hl.split('-')[0]}"
    url = f"https://news.google.com/rss?hl={hl}&gl={gl}&ceid={ceid}"
    parsed = feedparser.parse(url)
    out, seen = [], set()
    for e in parsed.entries[:limit * 2]:
        t = _clean_title(e.get("title", ""))
        key = t.lower()
        if t and key not in seen:
            seen.add(key)
            out.append(t)
        if len(out) >= limit:
            break
    return out


def trending_user(country):
    """Usuario de sistema (inactivo) dueño de las historias de tendencia de un país."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    username = f"__trending_{country.lower()}__"
    user, created = User.objects.get_or_create(
        username=username, defaults={"is_active": False})
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    return user


def is_trending_user(user):
    return bool(user and user.get_username().startswith("__trending_"))


def trending_feed(country):
    """Feed sintético donde aterrizan los artículos de tendencia del país."""
    from feeds.models import Feed, Source

    user = trending_user(country)
    source, _ = Source.objects.get_or_create(domain="trending.local", defaults={"name": "Tendencias"})
    feed, _ = Feed.objects.get_or_create(
        user=user, url=f"trending://{country.lower()}",
        defaults={"source": source, "title": f"Tendencias {country}", "enabled": False},
    )
    return feed


def active_countries():
    """Países a calcular: los elegidos por algún usuario + el default (u operador)."""
    from accounts.models import UserConfig

    codes = {resolve_country(None)}  # default / operador
    for cfg in UserConfig.objects.all().only("data"):
        c = (cfg.data.get("trending_country") or "").upper()
        if c in _BY_CODE:
            codes.add(c)
    return sorted(codes)
