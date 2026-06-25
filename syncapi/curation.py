"""Enriquecimiento de los artículos servidos por las APIs de sync (Fever/GReader).

Cuando el usuario activa el modo curación, inyectamos al final del HTML del artículo el
contexto/afirmaciones/sesgo, la noticia contrastada y las otras fuentes de su historia.
No se pueden añadir campos al protocolo, pero el cuerpo HTML sí lo controlamos nosotros,
así que la curación viaja a cualquier lector externo.
"""
from __future__ import annotations

import html as _html


def curation_enabled(user) -> bool:
    cfg = getattr(user, "config", None)
    return bool(cfg and cfg.data.get("sync_curation") == "1")


def enriched_html(article, user) -> str:
    base = article.best_text or ""
    if not curation_enabled(user):
        return base

    from stories.synthesis import render_markdown

    parts = [base, '<hr><p><strong>— Curación · NotisNotis —</strong></p>',
             f"<p><strong>Sesgo de la fuente:</strong> {_html.escape(article.source.get_bias_display())}</p>"]
    if article.context:
        parts.append(f"<h4>Contexto</h4><p>{_html.escape(article.context)}</p>")
    if article.framing_note:
        parts.append(f"<p><strong>Encuadre:</strong> {_html.escape(article.framing_note)}</p>")
    claims = "".join(
        f"<li>{_html.escape(c.get('text', ''))}</li>"
        for c in (article.claims or []) if c.get("text")
    )
    if claims:
        parts.append(f"<h4>Afirmaciones señaladas</h4><ul>{claims}</ul>")

    sa = article.stories.filter(story__user=user).select_related("story").first()
    if sa:
        story = sa.story
        if story.synthesis:
            parts.append(f"<h4>Noticia contrastada</h4>{render_markdown(story.synthesis)}")
        others = [
            x.article for x in
            story.story_articles.select_related("article", "article__source")
            if x.article_id != article.id
        ]
        if others:
            lis = "".join(
                f'<li><a href="{_html.escape(o.url or "")}">'
                f"{_html.escape(o.source.name)}: {_html.escape(o.title)}</a></li>"
                for o in others[:10]
            )
            parts.append(f"<h4>Otras fuentes ({len(others)})</h4><ul>{lis}</ul>")
    return "".join(parts)
