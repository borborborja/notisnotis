"""Motor de reglas: aplica acciones a artículos nuevos que cumplen condiciones."""
from __future__ import annotations

import re

from django.utils import timezone


def _compiled(rule):
    if not rule.pattern:
        return None
    try:
        return re.compile(rule.pattern, re.IGNORECASE)
    except re.error:
        return None


def load_rules(user):
    """Reglas activas del usuario, precompiladas: [(rule, regex|None)]."""
    return [(r, _compiled(r)) for r in user.rules.filter(enabled=True).select_related("feed", "category", "action_tag")]


def _matches(rule, regex, article):
    if rule.feed_id and article.feed_id != rule.feed_id:
        return False
    if rule.category_id and article.feed.category_id != rule.category_id:
        return False
    if regex is not None:
        if rule.match_in == "title":
            hay = article.title
        elif rule.match_in == "summary":
            hay = article.summary
        else:
            hay = f"{article.title}\n{article.summary}"
        if not regex.search(hay or ""):
            return False
    return True


def apply_rules(article, rules):
    """Aplica las reglas que casen. Devuelve True si modificó el artículo."""
    changed = False
    for rule, regex in rules:
        if not _matches(rule, regex, article):
            continue
        if rule.action_mark_read and not article.is_read:
            article.is_read = True
            article.read_at = timezone.now()
            changed = True
        if rule.action_star and not article.is_saved:
            article.is_saved = True
            changed = True
        if rule.action_tag_id:
            article.tags.add(rule.action_tag)
    if changed:
        article.save(update_fields=["is_read", "is_saved", "read_at"])
    return changed
