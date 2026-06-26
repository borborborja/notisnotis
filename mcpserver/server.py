"""Servidor MCP de facet.news (FastMCP).

Requiere Python >= 3.10 (dependencia del SDK `mcp`). Reutiliza la ORM de Django.
Autenticación por token de API: variable de entorno NOTISNOTIS_API_TOKEN → resuelve
el usuario y todas las tools filtran por él.

Arranque:
    NOTISNOTIS_API_TOKEN=<token> python manage.py run_mcp            # stdio
    NOTISNOTIS_API_TOKEN=<token> python manage.py run_mcp --http --port 8765
"""
from __future__ import annotations

import os

from django.utils import timezone


def _resolve_user():
    from accounts.models import ApiToken

    token = os.environ.get("NOTISNOTIS_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Define NOTISNOTIS_API_TOKEN con un token válido (Ajustes → Tokens).")
    try:
        api = ApiToken.objects.select_related("user").get(token=token)
    except ApiToken.DoesNotExist as exc:
        raise RuntimeError("Token de API inválido.") from exc
    api.last_used = timezone.now()
    api.save(update_fields=["last_used"])
    return api.user


def build_server():
    from mcp.server.fastmcp import FastMCP

    from articles.models import Article
    from stories.models import Story

    user = _resolve_user()
    mcp = FastMCP("notisnotis")

    def _story_dict(s, full=False):
        d = {
            "id": s.id,
            "headline": s.headline,
            "is_blindspot": s.is_blindspot,
            "blindspot_side": s.blindspot_side,
            "bias_distribution": s.bias_distribution,
            "sources": s.article_count,
            "last_updated": s.last_updated.isoformat(),
        }
        if full:
            d["neutral_summary"] = s.neutral_summary
            d["perspectives"] = s.perspectives
            d["articles"] = [
                {"id": sa.article.id, "title": sa.article.title, "source": sa.article.source.name,
                 "bias": sa.article.source.bias, "url": sa.article.url}
                for sa in s.story_articles.select_related("article", "article__source")
            ]
        return d

    def _article_dict(a, full=False):
        d = {
            "id": a.id, "title": a.title, "source": a.source.name, "bias": a.source.bias,
            "url": a.url, "published_at": a.published_at.isoformat() if a.published_at else None,
            "is_read": a.is_read, "is_saved": a.is_saved,
        }
        if full:
            d.update({
                "summary": a.summary, "body": a.best_text[:5000],
                "context": a.context, "claims": a.claims, "framing_note": a.framing_note,
            })
        return d

    @mcp.tool()
    def list_stories(filter: str = "recent", limit: int = 20) -> list:
        """Lista historias del usuario. filter: recent|blindspot."""
        qs = Story.objects.filter(user=user)
        if filter == "blindspot":
            qs = qs.filter(is_blindspot=True)
        return [_story_dict(s) for s in qs[:limit]]

    @mcp.tool()
    def get_story(story_id: int) -> dict:
        """Detalle de una historia: resumen neutral, perspectivas, sesgo y artículos."""
        s = Story.objects.filter(user=user, id=story_id).first()
        return _story_dict(s, full=True) if s else {"error": "no encontrada"}

    @mcp.tool()
    def search_articles(query: str, k: int = 10) -> list:
        """Búsqueda semántica de artículos por similitud de embedding."""
        from aiproviders.client import get_embed_client
        from stories.nn import top_k_articles

        vec = get_embed_client(user).embed([query])[0]
        return [{**_article_dict(a), "score": round(score, 3)}
                for score, a in top_k_articles(user, vec, k=k)]

    @mcp.tool()
    def list_articles(unread: bool = False, saved: bool = False, limit: int = 25) -> list:
        """Lista artículos del usuario. Filtros: unread, saved."""
        qs = Article.objects.filter(feed__user=user).select_related("source")
        if unread:
            qs = qs.filter(is_read=False)
        if saved:
            qs = qs.filter(is_saved=True)
        return [_article_dict(a) for a in qs[:limit]]

    @mcp.tool()
    def get_article(article_id: int) -> dict:
        """Detalle de un artículo con cuerpo y enriquecimiento."""
        a = Article.objects.filter(feed__user=user, id=article_id).select_related("source").first()
        return _article_dict(a, full=True) if a else {"error": "no encontrado"}

    @mcp.tool()
    def get_full_text(article_id: int) -> dict:
        """Recupera (si está habilitado) y devuelve el texto completo de un artículo."""
        from aiproviders.config import effective_config
        from articles.fulltext import populate_full_text

        a = Article.objects.filter(feed__user=user, id=article_id).first()
        if not a:
            return {"error": "no encontrado"}
        enabled = effective_config(user)["fulltext_enabled"]
        if not enabled:
            return {"error": "texto completo desactivado para este usuario"}
        ok = populate_full_text(a, enabled=enabled)
        return {"ok": ok, "source": a.fulltext_source, "full_text": a.full_text[:8000]}

    @mcp.tool()
    def list_blindspots(limit: int = 20) -> list:
        """Historias marcadas como blindspot."""
        return [_story_dict(s) for s in Story.objects.filter(user=user, is_blindspot=True)[:limit]]

    @mcp.tool()
    def list_feeds() -> list:
        """Feeds del usuario."""
        return [
            {"id": f.id, "title": f.title, "url": f.url, "source": f.source.name,
             "bias": f.source.bias, "enabled": f.enabled}
            for f in user.feeds.select_related("source")
        ]

    return mcp
