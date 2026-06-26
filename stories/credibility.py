"""Señal de credibilidad CONTEXTUAL de una fuente respecto a un suceso.

Combina fiabilidad factual + proximidad geográfica + libertad de prensa del país + propiedad
(estatal/independiente). Es informativa: alimenta badges en la UI y guía (no filtra) la síntesis.
"""
from __future__ import annotations

from feeds.press_freedom import label as press_label
from feeds.press_freedom import tier as press_tier

_FACT = {"high": 1.0, "mixed": 0.6, "low": 0.3}
_OWN = {"state": "medio estatal", "partisan": "medio partidista", "independent": "independiente"}


def context_label(source, story_country=""):
    """Etiqueta corta del contexto de una fuente (para prompts y tooltips)."""
    parts = []
    country = (getattr(source, "country", "") or "").upper()
    if country:
        parts.append("local" if country == (story_country or "").upper() and story_country else country)
    own = _OWN.get(getattr(source, "ownership", "") or "")
    if own and own != "independiente":
        parts.append(own)
    pl = press_label(country)
    if pl and pl != "prensa libre":
        parts.append(pl)
    return ", ".join(parts)


def source_signal(source, story_country=""):
    """Devuelve {weight, flags, notes} para una fuente respecto al país del suceso."""
    country = (getattr(source, "country", "") or "").upper()
    ownership = getattr(source, "ownership", "") or "unknown"
    press = press_tier(country)
    story_country = (story_country or "").upper()

    weight = _FACT.get((getattr(source, "factuality", "") or "").lower(), 0.5)
    flags, notes = [], []

    local = bool(country and story_country and country == story_country)
    if local:
        flags.append("local")
        # Proximidad útil solo si hay algo de libertad de prensa.
        weight += 0.25 if press in ("free", "partly_free") else 0.0

    if ownership == "state":
        flags.append("estatal")
        weight -= 0.5 if press == "not_free" else 0.15  # estatal en país censurado: fuerte recorte
    elif ownership == "partisan":
        flags.append("partidista")
        weight -= 0.1

    if press == "not_free":
        flags.append("baja libertad de prensa")
        if local:
            weight -= 0.2  # local + censura: precaución
    elif press == "partly_free" and local:
        notes.append("prensa parcialmente libre")

    weight = max(0.05, min(1.0, weight))
    return {"weight": round(weight, 2), "flags": flags, "country": country, "press": press}
