"""Parser de OPML → altas de Category + Source + Feed. Usa defusedxml (seguro XXE)."""
from __future__ import annotations

from urllib.parse import urlparse

from defusedxml.ElementTree import fromstring

from .models import Category, Feed, Source


def parse_opml(content: str):
    """Devuelve [{url, title, html_url, category}] recorriendo el árbol de outlines.

    Un <outline> con xmlUrl es un feed; su `category` es el texto del <outline> padre
    sin xmlUrl (carpeta). Los outlines sin xmlUrl con hijos se tratan como carpetas.
    """
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    root = fromstring(content)
    body = root.find("body")
    if body is None:
        return []

    out = []

    def walk(node, category):
        for outline in node.findall("outline"):
            url = outline.get("xmlUrl")
            label = (outline.get("title") or outline.get("text") or "").strip()
            if url:
                out.append(
                    {
                        "url": url.strip(),
                        "title": label,
                        "html_url": (outline.get("htmlUrl") or "").strip(),
                        "category": category,
                    }
                )
            else:
                # Carpeta: su etiqueta pasa a ser la categoría de los hijos.
                walk(outline, label or category)

    walk(body, None)
    return out


def _domain(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def import_opml_for_user(user, content: str):
    """Crea/actualiza Category, Source y Feed para el usuario. Devuelve (creados, omitidos)."""
    created, skipped = 0, 0
    cat_cache = {}
    for entry in parse_opml(content):
        url = entry["url"]
        ref_url = entry["html_url"] or url
        domain = _domain(ref_url) or _domain(url) or "unknown"
        source, _ = Source.objects.get_or_create(
            domain=domain,
            defaults={"name": entry["title"] or domain},
        )
        if not source.name:
            source.name = entry["title"] or domain
            source.save(update_fields=["name"])

        category = None
        cat_name = entry.get("category")
        if cat_name:
            if cat_name not in cat_cache:
                cat_cache[cat_name], _ = Category.objects.get_or_create(user=user, name=cat_name)
            category = cat_cache[cat_name]

        feed, was_created = Feed.objects.get_or_create(
            user=user,
            url=url,
            defaults={"source": source, "title": entry["title"], "category": category},
        )
        if was_created:
            created += 1
        else:
            # Asigna categoría si el feed existía sin ella.
            if category and feed.category_id is None:
                feed.category = category
                feed.save(update_fields=["category"])
            skipped += 1
    return created, skipped
