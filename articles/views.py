from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import UserConfig
from aiproviders.client import get_chat_client
from aiproviders.config import effective_config

from .ai_actions import LANGS, chat_reply, reading_prefs, summarize_article, translate_article
from .enrich import enrich_article
from .fulltext import populate_full_text
from .models import Article, Tag

VIEW_MODES = {"titles", "cards", "magazine"}
ITEM_TEMPLATES = {
    "titles": "articles/_item_titles.html",
    "cards": "articles/_item_cards.html",
    "magazine": "articles/_item_magazine.html",
}


def _pref(user, key, default=""):
    cfg = getattr(user, "config", None)
    return (cfg.data.get(key) if cfg else None) or default


def _set_pref(user, key, value):
    cfg, _ = UserConfig.objects.get_or_create(user=user)
    cfg.data[key] = value
    cfg.save(update_fields=["data"])


def _apply_search(qs, q):
    """Búsqueda con operadores (is:unread|read|saved, feed:<id>) + full-text."""
    from django.db import connection

    text_terms = []
    for tok in q.split():
        low = tok.lower()
        if low == "is:unread":
            qs = qs.filter(is_read=False)
        elif low == "is:read":
            qs = qs.filter(is_read=True)
        elif low == "is:saved":
            qs = qs.filter(is_saved=True)
        elif low.startswith("feed:") and low[5:].isdigit():
            qs = qs.filter(feed_id=low[5:])
        else:
            text_terms.append(tok)

    text = " ".join(text_terms).strip()
    if text:
        if connection.vendor == "postgresql":
            from django.contrib.postgres.search import SearchQuery, SearchVector

            qs = qs.annotate(_sv=SearchVector("title", "summary", "body")).filter(
                _sv=SearchQuery(text, search_type="websearch")
            )
        else:
            for term in text_terms:
                qs = qs.filter(
                    Q(title__icontains=term) | Q(summary__icontains=term) | Q(body__icontains=term)
                )
    return qs, f"Búsqueda: {q}"


def _filtered_articles(request):
    """Construye el queryset según los parámetros de la URL + título de la vista."""
    from stories.models import StoryArticle

    qs = (
        Article.objects.filter(feed__user=request.user)
        .select_related("source", "feed")
        .annotate(
            in_blindspot=Exists(
                StoryArticle.objects.filter(article=OuterRef("pk"), story__is_blindspot=True)
            )
        )
    )
    title = "Todos los artículos"

    feed_id = request.GET.get("feed")
    if feed_id:
        qs = qs.filter(feed_id=feed_id)
        feed = qs.first()
        title = (feed.feed.title or feed.source.name) if feed else "Feed"

    category_id = request.GET.get("category")
    if category_id == "none":
        qs = qs.filter(feed__category__isnull=True)
        title = "Sin categoría"
    elif category_id:
        qs = qs.filter(feed__category_id=category_id)
        from feeds.models import Category

        cat = Category.objects.filter(id=category_id, user=request.user).first()
        title = cat.name if cat else "Categoría"

    flt = request.GET.get("filter", "")
    if flt == "unread":
        qs = qs.filter(is_read=False)
        title = "No leídos"
    elif flt == "saved":
        qs = qs.filter(is_saved=True)
        title = "★ Guardados"

    tag_id = request.GET.get("tag")
    if tag_id:
        qs = qs.filter(tags__id=tag_id)
        tag = Tag.objects.filter(id=tag_id, user=request.user).first()
        title = f"#{tag.name}" if tag else "Etiqueta"

    q = request.GET.get("q", "").strip()
    if q:
        qs, title = _apply_search(qs, q)

    if request.GET.get("sort") == "oldest":
        qs = qs.order_by("published_at", "fetched_at")

    return qs, title


@login_required
def article_list(request):
    view = request.GET.get("view") or _pref(request.user, "ui_view_mode", "magazine")
    if view not in VIEW_MODES:
        view = "magazine"
    if request.GET.get("view") in VIEW_MODES:
        _set_pref(request.user, "ui_view_mode", view)

    qs, title = _filtered_articles(request)
    page = Paginator(qs, 30).get_page(request.GET.get("page"))

    params = request.GET.copy()
    params.pop("page", None)
    params.pop("view", None)

    ctx = {
        "page": page,
        "view": view,
        "item_template": ITEM_TEMPLATES[view],
        "list_title": title,
        "qparams": params.urlencode(),
        "all_params": request.GET.urlencode(),
        "sort": request.GET.get("sort", "newest"),
        "automark": reading_prefs(request.user)["auto_mark_scroll"],
    }
    # Scroll infinito: htmx pide solo los ítems de la página siguiente.
    if request.headers.get("HX-Request") and request.GET.get("page"):
        return render(request, "articles/_items.html", ctx)
    return render(request, "articles/article_list.html", ctx)


@login_required
def reading_pane(request, pk):
    """Panel de lectura (parcial htmx). Marca el artículo como leído."""
    article = get_object_or_404(
        Article.objects.select_related("source", "feed"), pk=pk, feed__user=request.user
    )
    if not article.is_read:
        article.is_read = True
        article.read_at = timezone.now()
        article.save(update_fields=["is_read", "read_at"])

    if not article.is_enriched and effective_config(request.user)["enrich_mode"] == "on_demand":
        try:
            enrich_article(article, client=get_chat_client(request.user))
        except Exception:  # noqa: BLE001 - no romper la lectura si falla la IA
            pass

    prefs = reading_prefs(request.user)
    if prefs["auto_translate"] and not article.translated_at:
        try:
            translate_article(article, prefs["lang"], client=get_chat_client(request.user))
        except Exception:  # noqa: BLE001
            pass
    if prefs["auto_summarize"] and not article.summarized_at:
        try:
            summarize_article(article, client=get_chat_client(request.user))
        except Exception:  # noqa: BLE001
            pass

    return render(request, "articles/_reading_pane.html", _reading_ctx(request, article))


def _reading_ctx(request, article):
    story = article.stories.filter(story__user=request.user).select_related("story").first()
    return {
        "article": article,
        "story_link": story.story if story else None,
        "fulltext_enabled": effective_config(request.user)["fulltext_enabled"],
        "show_original": request.GET.get("original") == "1",
        "langs": LANGS,
        "prefs": reading_prefs(request.user),
        "article_tags": list(article.tags.all()),
        "all_tags": list(Tag.objects.filter(user=request.user)),
        "webhook_url": (getattr(request.user, "config", None) and request.user.config.data.get("webhook_url")) or "",
    }


@login_required
def article_detail(request, pk):
    """Página completa de un artículo (acceso directo / sin htmx)."""
    article = get_object_or_404(
        Article.objects.select_related("source", "feed"), pk=pk, feed__user=request.user
    )
    return render(request, "articles/article_detail.html", _reading_ctx(request, article))


@login_required
@require_POST
def fetch_fulltext(request, pk):
    article = get_object_or_404(Article, pk=pk, feed__user=request.user)
    enabled = effective_config(request.user)["fulltext_enabled"]
    if enabled:
        try:
            populate_full_text(article, enabled=enabled)
        except Exception as exc:  # noqa: BLE001
            messages.error(request, f"Error: {exc}")
    article = Article.objects.select_related("source", "feed").get(pk=pk)
    return render(request, "articles/_reading_pane.html", _reading_ctx(request, article))


@login_required
@require_POST
def toggle_saved(request, pk):
    article = get_object_or_404(Article, pk=pk, feed__user=request.user)
    article.is_saved = not article.is_saved
    article.save(update_fields=["is_saved"])
    if request.headers.get("HX-Request"):
        return render(request, "articles/_reading_pane.html", _reading_ctx(request, article))
    return redirect("articles:detail", pk=pk)


@login_required
@require_POST
def mark_read(request, pk):
    article = get_object_or_404(Article, pk=pk, feed__user=request.user)
    article.is_read = request.POST.get("read", "1") == "1"
    article.read_at = timezone.now() if article.is_read else None
    article.save(update_fields=["is_read", "read_at"])
    return render(request, "articles/_reading_pane.html", _reading_ctx(request, article))


@login_required
@require_POST
def mark_all_read(request):
    qs, _ = _filtered_articles(request)
    qs.filter(is_read=False).update(is_read=True, read_at=timezone.now())
    messages.success(request, "Marcados como leídos.")
    return redirect(f"{request.path}?{request.POST.get('params', '')}")


READING_PREF_VALUES = {
    "read_size": {"s", "m", "l"},
    "read_font": {"sans", "serif"},
    "read_width": {"narrow", "normal", "wide"},
}


@login_required
@require_POST
def set_reading_pref(request):
    """Guarda una preferencia de lectura (tamaño/fuente/ancho). Devuelve 204."""
    key = request.POST.get("key", "")
    value = request.POST.get("value", "")
    if key in READING_PREF_VALUES and value in READING_PREF_VALUES[key]:
        cfg, _ = UserConfig.objects.get_or_create(user=request.user)
        cfg.data[key] = value
        cfg.save(update_fields=["data"])
    return HttpResponse(status=204)


@login_required
@require_POST
def mark_seen(request, pk):
    """Marca leído de forma ligera (auto-marcar al hacer scroll). Devuelve 204."""
    Article.objects.filter(pk=pk, feed__user=request.user, is_read=False).update(
        is_read=True, read_at=timezone.now()
    )
    return HttpResponse(status=204)


@login_required
@require_POST
def translate(request, pk):
    article = get_object_or_404(Article.objects.select_related("source", "feed"), pk=pk, feed__user=request.user)
    lang = request.POST.get("lang") or reading_prefs(request.user)["lang"]
    try:
        translate_article(article, lang, client=get_chat_client(request.user))
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f"No se pudo traducir: {exc}")
    return render(request, "articles/_reading_pane.html", _reading_ctx(request, article))


@login_required
@require_POST
def summarize(request, pk):
    article = get_object_or_404(Article.objects.select_related("source", "feed"), pk=pk, feed__user=request.user)
    try:
        summarize_article(article, client=get_chat_client(request.user))
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f"No se pudo resumir: {exc}")
    return render(request, "articles/_reading_pane.html", _reading_ctx(request, article))


@login_required
@require_POST
def tag_add(request, pk):
    article = get_object_or_404(Article.objects.select_related("source", "feed"), pk=pk, feed__user=request.user)
    name = request.POST.get("name", "").strip()[:100]
    if name:
        tag, _ = Tag.objects.get_or_create(user=request.user, name=name)
        article.tags.add(tag)
    return render(request, "articles/_reading_pane.html", _reading_ctx(request, article))


@login_required
@require_POST
def tag_remove(request, pk):
    article = get_object_or_404(Article.objects.select_related("source", "feed"), pk=pk, feed__user=request.user)
    article.tags.remove(*Tag.objects.filter(user=request.user, id=request.POST.get("tag_id")))
    return render(request, "articles/_reading_pane.html", _reading_ctx(request, article))


@login_required
def export_markdown(request, pk):
    article = get_object_or_404(Article.objects.select_related("source"), pk=pk, feed__user=request.user)
    from django.utils.html import strip_tags

    body = strip_tags(article.best_text)
    md = f"# {article.title}\n\n> {article.source.name} · {article.url}\n\n{body}\n"
    resp = HttpResponse(md, content_type="text/markdown; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="article-{article.pk}.md"'
    return resp


@login_required
@require_POST
def send_webhook(request, pk):
    """Envía el artículo (JSON) a la URL configurada por el usuario (read-it-later / automatización)."""
    import requests

    article = get_object_or_404(Article.objects.select_related("source", "feed"), pk=pk, feed__user=request.user)
    url = (getattr(request.user, "config", None) and request.user.config.data.get("webhook_url")) or ""
    if not url:
        messages.error(request, "Configura una URL de webhook en Ajustes → Notificaciones.")
    else:
        try:
            requests.post(url, json={
                "title": article.title, "url": article.url, "source": article.source.name,
                "summary": article.summary, "published_at": article.published_at.isoformat() if article.published_at else None,
            }, timeout=15)
            messages.success(request, "Enviado al webhook.")
        except Exception as exc:  # noqa: BLE001
            messages.error(request, f"No se pudo enviar: {exc}")
    return render(request, "articles/_reading_pane.html", _reading_ctx(request, article))


@login_required
def chat_panel(request, pk):
    article = get_object_or_404(Article.objects.select_related("source", "feed"), pk=pk, feed__user=request.user)
    key = f"chat_{pk}"
    if request.GET.get("reset"):
        request.session.pop(key, None)
    history = request.session.get(key, [])
    return render(request, "articles/_chat.html", {"article": article, "history": history})


@login_required
@require_POST
def chat_message(request, pk):
    article = get_object_or_404(Article.objects.select_related("source", "feed"), pk=pk, feed__user=request.user)
    key = f"chat_{pk}"
    history = request.session.get(key, [])
    msg = request.POST.get("message", "").strip()
    if msg:
        history.append({"role": "user", "content": msg})
        try:
            reply = chat_reply(article, request.user, history)
        except Exception as exc:  # noqa: BLE001
            reply = f"⚠ Error de la IA: {exc}"
        history.append({"role": "assistant", "content": reply})
        request.session[key] = history
        request.session.modified = True
    return render(request, "articles/_chat_thread.html", {"article": article, "history": history})
