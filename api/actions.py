"""Acciones de IA on-demand sobre un artículo: resumir, traducir, contexto, chat."""
from __future__ import annotations

from django.views.decorators.http import require_http_methods

from .auth import api_token
from .helpers import body_json, err, ok, require_module
from .serializers import article_dict

MODULE = "curation"


def _article(request, pk):
    from articles.models import Article

    return (Article.objects.filter(feed__user=request.api_user, pk=pk)
            .select_related("source", "feed").first())


def _guard_and_article(request, pk):
    g = require_module(request.api_user, MODULE)
    if g:
        return None, g
    a = _article(request, pk)
    if not a:
        return None, err("not_found", "Artículo no encontrado.", status=404)
    return a, None


@api_token
@require_http_methods(["POST"])
def summarize(request, pk):
    a, e = _guard_and_article(request, pk)
    if e:
        return e
    from aiproviders.client import get_chat_client
    from articles.ai_actions import summarize_article

    try:
        summarize_article(a, client=get_chat_client(request.api_user))
    except Exception as exc:  # noqa: BLE001
        return err("ai_failed", str(exc), status=502)
    return ok({"tldr": a.tldr, "article": article_dict(a, user=request.api_user, full=True)})


@api_token
@require_http_methods(["POST"])
def translate(request, pk):
    a, e = _guard_and_article(request, pk)
    if e:
        return e
    from aiproviders.client import get_chat_client
    from articles.ai_actions import reading_prefs, translate_article

    lang = body_json(request).get("lang") or reading_prefs(request.api_user)["lang"]
    try:
        translate_article(a, lang, client=get_chat_client(request.api_user))
    except Exception as exc:  # noqa: BLE001
        return err("ai_failed", str(exc), status=502)
    return ok({"article": article_dict(a, user=request.api_user, full=True)})


@api_token
@require_http_methods(["POST"])
def context(request, pk):
    a, e = _guard_and_article(request, pk)
    if e:
        return e
    from aiproviders.client import get_chat_client
    from articles.enrich import enrich_article

    try:
        enrich_article(a, client=get_chat_client(request.api_user))
    except Exception as exc:  # noqa: BLE001
        return err("ai_failed", str(exc), status=502)
    return ok({"context": a.context, "claims": a.claims, "framing_note": a.framing_note})


@api_token
@require_http_methods(["POST"])
def chat(request, pk):
    a, e = _guard_and_article(request, pk)
    if e:
        return e
    from articles.ai_actions import chat_reply

    data = body_json(request)
    history = data.get("history")
    if not history:
        msg = (data.get("message") or "").strip()
        if not msg:
            return err("bad_request", "Falta 'message' o 'history'.")
        history = [{"role": "user", "content": msg}]
    try:
        reply = chat_reply(a, request.api_user, history)
    except Exception as exc:  # noqa: BLE001
        return err("ai_failed", str(exc), status=502)
    return ok({"reply": reply})
