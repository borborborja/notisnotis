"""Lógica de los feeds con IA: generar consultas, buscar, puntuar relevancia y
materializar las propuestas aceptadas como artículos del lector.
"""
from __future__ import annotations

import hashlib

from django.utils import timezone

from aiproviders.client import get_chat_client
from .models import AIFeedCandidate, AIFeedExample
from .search import web_search

QUERY_SYSTEM = (
    "Conviertes un interés del usuario en 3-5 consultas de búsqueda web efectivas para "
    "encontrar NOTICIAS recientes. Variadas y específicas, en el idioma de la descripción. "
    'Devuelve SOLO JSON: {"queries": ["...", "..."]}.'
)
QUERY_USER = "DESCRIPCIÓN DEL INTERÉS:\n{desc}\n\nLE HAN ENCAJADO TITULARES COMO:\n{pos}\n\nGenera las consultas."

SCORE_SYSTEM = (
    "Evalúas la relevancia de titulares respecto al interés del usuario, teniendo en cuenta "
    "ejemplos de lo que le encaja y lo que no. Para cada ítem da un score 0-10 y una razón "
    'breve. Devuelve SOLO JSON: {"scores": [{"i": 0, "score": 8, "reason": "..."}]}.'
)
SCORE_USER = (
    "INTERÉS:\n{desc}\n\nLE ENCAJAN:\n{pos}\n\nNO LE ENCAJAN:\n{neg}\n\nCANDIDATOS:\n{items}\n\n"
    "Evalúa TODOS los candidatos por su índice."
)


def ensure_feed(ai_feed):
    """Crea (perezosamente) el Feed sintético donde aterrizan los artículos aceptados."""
    if ai_feed.feed_id:
        return ai_feed.feed
    from feeds.models import Feed, Source

    source, _ = Source.objects.get_or_create(domain="aifeed.local", defaults={"name": "Feeds con IA"})
    feed = Feed.objects.create(
        user=ai_feed.user, source=source, url=f"aifeed://{ai_feed.pk}",
        title=ai_feed.name, enabled=False,  # no es RSS: fetch_feeds lo ignora
    )
    ai_feed.feed = feed
    ai_feed.save(update_fields=["feed"])
    return feed


def generate_queries(ai_feed, client):
    pos = "\n".join(f"- {e.title}" for e in ai_feed.examples.filter(relevant=True)[:8]) or "(ninguno)"
    try:
        data = client.chat([
            {"role": "system", "content": QUERY_SYSTEM},
            {"role": "user", "content": QUERY_USER.format(desc=ai_feed.description, pos=pos)},
        ], json=True)
    except Exception:  # noqa: BLE001
        data = {}
    qs = data.get("queries") if isinstance(data, dict) else None
    if isinstance(qs, list) and qs:
        return [str(q)[:200] for q in qs][:6]
    return [ai_feed.description[:200]]


def score_candidates(ai_feed, client, candidates):
    """Devuelve dict url -> {score, reason}. Lo no puntuado por el LLM pasa con min_score."""
    pos = "\n".join(f"- {e.title}" for e in ai_feed.examples.filter(relevant=True)[:8]) or "(ninguno)"
    neg = "\n".join(f"- {e.title}" for e in ai_feed.examples.filter(relevant=False)[:8]) or "(ninguno)"
    items = "\n".join(f"{i}) {c['title']} — {c['snippet'][:200]}" for i, c in enumerate(candidates))
    try:
        data = client.chat([
            {"role": "system", "content": SCORE_SYSTEM},
            {"role": "user", "content": SCORE_USER.format(desc=ai_feed.description, pos=pos, neg=neg, items=items)},
        ], json=True)
    except Exception:  # noqa: BLE001
        data = {}
    out = {}
    for s in (data.get("scores") or []) if isinstance(data, dict) else []:
        try:
            out[candidates[int(s["i"])]["url"]] = {
                "score": max(0, min(10, int(s.get("score", 0)))),
                "reason": str(s.get("reason", ""))[:300],
                "llm": True,  # puntuado realmente por el LLM (requisito para auto-aceptar)
            }
        except (ValueError, TypeError, KeyError, IndexError):
            continue
    for c in candidates:
        out.setdefault(c["url"], {"score": ai_feed.min_score, "reason": "", "llm": False})
    return out


# Nº mínimo de aprobaciones para considerar el feed "entrenado" (habilita auto-aceptar).
TRAIN_MIN = 5


def run_search(ai_feed, *, per_query=12):
    """Busca, dedup, puntúa y: auto-añade los de alta confianza (si está entrenado) o crea
    propuestas para revisar. Devuelve dict {proposed, auto}."""
    from articles.models import Article

    client = get_chat_client(ai_feed.user)
    seen, results = set(), []
    for q in generate_queries(ai_feed, client):
        try:
            for r in web_search(q, k=per_query):
                if r["url"] not in seen:
                    seen.add(r["url"])
                    results.append(r)
        except Exception:  # noqa: BLE001 - una query fallida no aborta el resto
            continue

    existing = set(Article.objects.filter(feed__user=ai_feed.user).exclude(url="").values_list("url", flat=True))
    existing |= set(ai_feed.candidates.values_list("url", flat=True))
    fresh = [r for r in results if r["url"] not in existing]

    proposed, auto = 0, 0
    if fresh:
        trained = ai_feed.examples.filter(relevant=True).count() >= TRAIN_MIN
        auto_on = trained and ai_feed.auto_accept_score <= 10
        scored = score_candidates(ai_feed, client, fresh)
        for r in fresh:
            sc = scored.get(r["url"], {})
            score = sc.get("score", 0)
            if score < ai_feed.min_score:
                continue
            if auto_on and sc.get("llm") and score >= ai_feed.auto_accept_score:
                _auto_accept(ai_feed, r, score, sc.get("reason", ""))
                auto += 1
            else:
                _, made = AIFeedCandidate.objects.get_or_create(
                    ai_feed=ai_feed, url=r["url"],
                    defaults={"title": r["title"], "snippet": r["snippet"],
                              "score": score or ai_feed.min_score, "reason": sc.get("reason", "")},
                )
                proposed += int(made)
    ai_feed.last_run = timezone.now()
    ai_feed.save(update_fields=["last_run"])
    return {"proposed": proposed, "auto": auto}


def _materialize_article(ai_feed, url, title, snippet):
    """Crea (o recupera) el Article real en el feed sintético a partir de una noticia."""
    from articles.models import Article
    from feeds.models import Source
    from feeds.opml import _domain

    feed = ensure_feed(ai_feed)
    domain = _domain(url) or "unknown"
    source, _ = Source.objects.get_or_create(domain=domain, defaults={"name": domain})
    guid = "ai-" + hashlib.sha1(url.encode()).hexdigest()[:24]
    article, _ = Article.objects.get_or_create(
        feed=feed, guid=guid,
        defaults={"source": source, "url": url, "title": title,
                  "summary": snippet, "published_at": timezone.now()},
    )
    return article


def _auto_accept(ai_feed, r, score, reason):
    """Añade automáticamente una noticia de alta confianza (sin crear ejemplo de entrenamiento)."""
    article = _materialize_article(ai_feed, r["url"], r["title"], r["snippet"])
    AIFeedCandidate.objects.get_or_create(
        ai_feed=ai_feed, url=r["url"],
        defaults={"title": r["title"], "snippet": r["snippet"], "score": score,
                  "reason": reason, "status": AIFeedCandidate.ACCEPTED, "article": article},
    )
    return article


def accept_candidate(candidate):
    """Crea un Article real en el feed sintético y guarda el ejemplo + (entrena)."""
    ai = candidate.ai_feed
    article = _materialize_article(ai, candidate.url, candidate.title, candidate.snippet)
    candidate.article = article
    candidate.status = AIFeedCandidate.ACCEPTED
    candidate.save(update_fields=["article", "status"])
    AIFeedExample.objects.create(
        ai_feed=ai, title=candidate.title, snippet=candidate.snippet, url=candidate.url, relevant=True)
    return article


def reject_candidate(candidate):
    candidate.status = AIFeedCandidate.REJECTED
    candidate.save(update_fields=["status"])
    AIFeedExample.objects.create(
        ai_feed=candidate.ai_feed, title=candidate.title, snippet=candidate.snippet,
        url=candidate.url, relevant=False)
