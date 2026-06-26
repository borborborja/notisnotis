"""API de curación IA: historias, tendencias, feeds IA (+entrenar), temas, relacionadas."""
from __future__ import annotations

from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from .auth import api_token
from .helpers import as_int, body_json, err, ok, param, require_module
from .serializers import (aifeed_dict, article_dict, candidate_dict, story_dict, topic_dict)

MODULE = "curation"


def _guard(request):
    return require_module(request.api_user, MODULE)


# --- historias ---
@api_token
@require_GET
def stories(request):
    if (g := _guard(request)):
        return g
    from django.db.models import Count
    from stories.models import Story

    qs = (Story.objects.filter(user=request.api_user)
          .annotate(n=Count("story_articles")).filter(n__gte=2))
    if param(request, "filter") == "blindspot":
        qs = qs.filter(is_blindspot=True)
    qs = qs.order_by("-last_updated")
    try:
        limit = min(int(param(request, "limit", "30")), 100)
    except ValueError:
        limit = 30
    return ok([story_dict(s, user=request.api_user) for s in qs[:limit]])


@api_token
@require_GET
def story_detail(request, pk):
    if (g := _guard(request)):
        return g
    from stories.models import Story

    s = Story.objects.filter(user=request.api_user, pk=pk).first()
    if not s:
        return err("not_found", "Historia no encontrada.", status=404)
    return ok(story_dict(s, user=request.api_user, full=True))


# --- tendencias (globales) ---
@api_token
@require_GET
def trending(request):
    if (g := _guard(request)):
        return g
    from django.db.models import Count
    from stories.models import Story
    from stories.trending import resolve_country, trending_user

    cc = (param(request, "country") or resolve_country(request.api_user)).upper()
    tu = trending_user(cc)
    qs = (Story.objects.filter(user=tu).annotate(n=Count("story_articles"))
          .filter(n__gte=2).order_by("-n", "-last_updated")[:40])
    return ok([story_dict(s) for s in qs], country=cc)


@api_token
@require_GET
def trending_detail(request, pk):
    if (g := _guard(request)):
        return g
    from stories.models import Story
    from stories.trending import is_trending_user

    s = Story.objects.filter(pk=pk).first()
    if not s or not is_trending_user(s.user):
        return err("not_found", "Tendencia no encontrada.", status=404)
    return ok(story_dict(s, full=True))


@api_token
@require_GET
def trending_countries(request):
    if (g := _guard(request)):
        return g
    from stories.trending import COUNTRIES, resolve_country

    return ok([{"code": c[0], "label": c[1]} for c in COUNTRIES],
              current=resolve_country(request.api_user))


# --- feeds IA ---
@api_token
@require_http_methods(["GET", "POST"])
def aifeeds(request):
    if (g := _guard(request)):
        return g
    from aifeeds.models import AIFeed

    if request.method == "GET":
        return ok([aifeed_dict(a) for a in AIFeed.objects.filter(user=request.api_user)])
    data = body_json(request)
    name = (data.get("name") or "").strip()[:200]
    desc = (data.get("description") or "").strip()
    if not name or not desc:
        return err("bad_request", "Faltan 'name' y/o 'description'.")
    af = AIFeed.objects.create(user=request.api_user, name=name, description=desc)
    return ok(aifeed_dict(af, full=True))


@api_token
@require_http_methods(["GET", "PATCH", "DELETE"])
def aifeed_detail(request, pk):
    if (g := _guard(request)):
        return g
    from aifeeds.models import AIFeed

    af = AIFeed.objects.filter(user=request.api_user, pk=pk).first()
    if not af:
        return err("not_found", "Feed IA no encontrado.", status=404)
    if request.method == "DELETE":
        af.delete()
        return ok({"deleted": pk})
    if request.method == "PATCH":
        data = body_json(request)
        fields = []
        if "min_score" in data and as_int(data["min_score"]) is not None:
            af.min_score = max(0, min(10, as_int(data["min_score"]))); fields.append("min_score")
        if "auto_accept_score" in data and as_int(data["auto_accept_score"]) is not None:
            af.auto_accept_score = max(0, min(11, as_int(data["auto_accept_score"]))); fields.append("auto_accept_score")
        if "enabled" in data:
            af.enabled = bool(data["enabled"]); fields.append("enabled")
        if fields:
            af.save(update_fields=fields)
    cands = af.candidates.order_by("-created_at")[:50]
    d = aifeed_dict(af, full=True)
    d["candidates"] = [candidate_dict(c) for c in cands]
    return ok(d)


@api_token
@require_http_methods(["POST"])
def aifeed_search(request, pk):
    if (g := _guard(request)):
        return g
    from aifeeds.models import AIFeed
    from aifeeds.services import run_search

    af = AIFeed.objects.filter(user=request.api_user, pk=pk).first()
    if not af:
        return err("not_found", "Feed IA no encontrado.", status=404)
    try:
        res = run_search(af)
    except Exception as exc:  # noqa: BLE001
        return err("search_failed", str(exc), status=502)
    return ok(res)


@api_token
@require_http_methods(["POST"])
def candidate_decide(request, pk):
    """{decision: 'accept'|'reject'} — entrena el algoritmo."""
    if (g := _guard(request)):
        return g
    from aifeeds.models import AIFeedCandidate
    from aifeeds.services import accept_candidate, reject_candidate

    cand = AIFeedCandidate.objects.filter(ai_feed__user=request.api_user, pk=pk).first()
    if not cand:
        return err("not_found", "Candidato no encontrado.", status=404)
    decision = body_json(request).get("decision")
    if decision == "accept":
        accept_candidate(cand)
    elif decision == "reject":
        reject_candidate(cand)
    else:
        return err("bad_request", "decision debe ser 'accept' o 'reject'.")
    return ok(candidate_dict(cand))


# --- temas ---
@api_token
@require_http_methods(["GET", "POST"])
def topics(request):
    if (g := _guard(request)):
        return g
    from stories.models import Topic

    if request.method == "GET":
        return ok([topic_dict(t) for t in Topic.objects.filter(user=request.api_user)])
    data = body_json(request)
    name = (data.get("name") or "").strip()[:200]
    kw = (data.get("keywords") or "").strip()[:500]
    if not name:
        return err("bad_request", "Falta 'name'.")
    t = Topic.objects.create(user=request.api_user, name=name, keywords=kw,
                             notify=bool(data.get("notify")))
    return ok(topic_dict(t))


@api_token
@require_http_methods(["DELETE"])
def topic_delete(request, pk):
    if (g := _guard(request)):
        return g
    from stories.models import Topic

    Topic.objects.filter(user=request.api_user, pk=pk).delete()
    return ok({"deleted": pk})


# --- relacionadas (umbral ya aplicado) ---
@api_token
@require_GET
def related(request, pk):
    if (g := _guard(request)):
        return g
    from articles.models import Article
    from articles.ai_actions import related_articles

    a = Article.objects.filter(feed__user=request.api_user, pk=pk).first()
    if not a:
        return err("not_found", "Artículo no encontrado.", status=404)
    rel = related_articles(a, request.api_user)
    out = []
    for x in rel:
        d = article_dict(x, user=request.api_user)
        d["rel_score"] = getattr(x, "rel_score", None)
        out.append(d)
    return ok(out)
