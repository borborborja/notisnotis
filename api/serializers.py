"""Serializadores JSON de la API. Sirven el contenido que el servidor YA tiene."""
from __future__ import annotations

from .helpers import iso


def source_dict(s):
    if not s:
        return None
    return {
        "id": s.id, "name": s.name, "domain": s.domain,
        "bias": s.bias, "factuality": s.factuality,
        "country": s.country, "ownership": s.ownership,
        "favicon": s.favicon or "",
    }


def feed_dict(f, unread=None):
    d = {
        "id": f.id, "title": f.title or (f.source.name if f.source_id else ""),
        "url": f.url, "kind": f.kind, "category_id": f.category_id,
        "enabled": f.enabled, "image_url": f.image_url,
        "description": f.description, "last_fetched": iso(f.last_fetched),
        "playback_speed": f.playback_speed, "skip_intro": f.skip_intro, "skip_outro": f.skip_outro,
        "source": source_dict(f.source) if f.source_id else None,
    }
    if unread is not None:
        d["unread"] = unread
    return d


def category_dict(c, unread=None):
    d = {"id": c.id, "name": c.name, "position": c.position}
    if unread is not None:
        d["unread"] = unread
    return d


def tag_dict(t):
    return {"id": t.id, "name": t.name}


def article_dict(a, user=None, full=False):
    """Artículo con su CONTENIDO almacenado y su estado (sin re-descargar de origen)."""
    from syncapi.curation import sync_body

    d = {
        "id": a.id, "feed_id": a.feed_id, "guid": a.guid, "url": a.url,
        "title": a.title, "summary": a.summary,
        "body": sync_body(a, user) if user else a.best_text,
        "published_at": iso(a.published_at), "fetched_at": iso(a.fetched_at),
        "updated_at": iso(a.updated_at), "read_at": iso(a.read_at),
        "is_read": a.is_read, "is_saved": a.is_saved,
        "reading_minutes": a.reading_minutes,
        "image_url": a.image_url, "source": source_dict(a.source) if a.source_id else None,
        # Campos de podcast/episodio
        "enclosure_url": a.enclosure_url, "enclosure_type": a.enclosure_type,
        "duration": a.duration, "play_position": a.play_position,
        "play_updated_at": iso(a.play_updated_at),
        "tags": [t.name for t in a.tags.all()],
    }
    if full:
        d.update({
            "full_text": a.full_text, "fulltext_source": a.fulltext_source,
            "context": a.context, "claims": a.claims, "framing_note": a.framing_note,
            "is_enriched": a.is_enriched,
            "tldr": a.tldr,
            "translated_title": a.translated_title, "translated_body": a.translated_body,
            "translation_lang": a.translation_lang,
            "chapters": a.chapters,
        })
    return d


def episode_dict(a, user=None, full=False):
    """Alias semántico para episodios de podcast (es un Article con enclosure)."""
    return article_dict(a, user=user, full=full)


def queue_dict(q, user=None):
    return {"position": q.position, "added_at": iso(q.added_at),
            "episode": article_dict(q.article, user=user)}


def _coverage(story, user):
    from stories.credibility import source_signal

    out = []
    for sa in story.story_articles.select_related("article", "article__source"):
        art = sa.article
        sig = source_signal(art.source, story.location_country)
        out.append({
            "id": art.id, "title": art.title, "url": art.url,
            "source": source_dict(art.source),
            "credibility_flags": sig["flags"], "similarity": round(sa.similarity, 3),
        })
    return out


def story_dict(s, user=None, full=False):
    d = {
        "id": s.id, "headline": s.headline,
        "is_blindspot": s.is_blindspot, "blindspot_side": s.blindspot_side,
        "bias_distribution": s.bias_distribution, "location_country": s.location_country,
        "n_sources": s.story_articles.count() if full else None,
        "last_updated": iso(s.last_updated), "first_seen": iso(s.first_seen),
    }
    if full:
        from stories.synthesis import render_markdown

        d.update({
            "neutral_summary": s.neutral_summary, "perspectives": s.perspectives,
            "synthesis": s.synthesis, "synthesis_html": render_markdown(s.synthesis),
            "synthesized_at": iso(s.synthesized_at),
            "coverage": _coverage(s, user),
        })
    return d


def aifeed_dict(af, full=False):
    d = {
        "id": af.id, "name": af.name, "description": af.description,
        "enabled": af.enabled, "feed_id": af.feed_id,
        "min_score": af.min_score, "auto_accept_score": af.auto_accept_score,
        "last_run": iso(af.last_run),
    }
    if full:
        d["examples"] = af.examples.count()
    return d


def candidate_dict(c):
    return {
        "id": c.id, "url": c.url, "title": c.title, "snippet": c.snippet,
        "score": c.score, "reason": c.reason, "status": c.status,
        "article_id": c.article_id, "created_at": iso(c.created_at),
    }


def topic_dict(t):
    return {"id": t.id, "name": t.name, "keywords": t.keywords, "notify": t.notify}
