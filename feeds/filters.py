"""Reglas de filtrado (block/keep) y deduplicado, inspirado en miniflux."""
from __future__ import annotations

import re


def compile_rules(text):
    """Compila reglas (una regex por línea, case-insensitive). Ignora las inválidas."""
    rules = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rules.append(re.compile(line, re.IGNORECASE))
        except re.error:
            continue
    return rules


def is_blocked(title, summary, block_rules, keep_rules):
    """True si el artículo debe descartarse según las reglas."""
    haystack = f"{title}\n{summary}"
    if any(r.search(haystack) for r in block_rules):
        return True
    if keep_rules and not any(r.search(haystack) for r in keep_rules):
        return True
    return False


def filter_prefs(user):
    cfg = getattr(user, "config", None)
    data = cfg.data if cfg else {}
    return {
        "block": compile_rules(data.get("block_rules", "")),
        "keep": compile_rules(data.get("keep_rules", "")),
        "dedupe": data.get("dedupe", "off"),  # off|url|title
    }
