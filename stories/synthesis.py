"""Redacción de una "noticia contrastada" a partir de la cobertura de varias fuentes.

Genera UN artículo neutral, con estructura narrativa y las ideas clave en negrita, usando
solo lo que aportan las fuentes (sin juicios de valor). Salida en markdown, que se renderiza
a HTML de forma segura (escapando primero) para mostrarla en el lector de la historia.
"""
from __future__ import annotations

import html
import re

from django.utils import timezone

from aiproviders.client import get_chat_client

SYSTEM = (
    "Eres un periodista que redacta UNA sola noticia contrastada a partir de la cobertura "
    "de varios medios sobre el mismo suceso. Reglas estrictas: "
    "1) Neutral, SIN juicios de valor ni opinión. "
    "2) Estructura narrativa clara: entradilla que resuma lo esencial y luego desarrollo. "
    "3) Resalta las ideas clave en **negrita**. "
    "4) Usa markdown: '## ' para subtítulos, párrafos separados por línea en blanco, listas "
    "con '- ' si procede. "
    "5) NO inventes datos: usa solo lo que aportan las fuentes; si no hay un dato, no lo pongas. "
    "6) Cuando las fuentes difieran o aporten ángulos distintos, indícalo de forma objetiva "
    "('según X…', 'mientras que Y…'). "
    "Devuelve SOLO el artículo en markdown, sin preámbulos."
)


def _coverage(story, max_articles=12, per_article=1500):
    lines = []
    sas = (story.story_articles.select_related("article", "article__source")
           .order_by("article__published_at"))
    for sa in sas[:max_articles]:
        a = sa.article
        text = (a.best_text or "")[:per_article].replace("\n", " ").strip()
        when = a.published_at.date().isoformat() if a.published_at else "s/f"
        lines.append(f"## {a.source.name} ({a.source.get_bias_display()}, {when})\n{a.title}\n{text}")
    return "\n\n".join(lines)


def generate_synthesis(story, client=None):
    client = client or get_chat_client(story.user)
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"TEMA: {story.headline}\n\nFUENTES Y SU COBERTURA:\n"
                                    f"{_coverage(story)}\n\nRedacta la noticia contrastada."},
    ]
    story.synthesis = (client.chat(messages) or "").strip()
    story.synthesized_at = timezone.now()
    story.save(update_fields=["synthesis", "synthesized_at"])
    return story


def _inline(s):
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
    return s.replace("\n", "<br>")


def render_markdown(text):
    """Markdown mínimo → HTML seguro (escapa primero; soporta ##, **, listas, párrafos)."""
    text = html.escape(text or "").strip()
    if not text:
        return ""
    blocks = re.split(r"\n\s*\n", text)
    out = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        if block.startswith("### "):
            out.append(f"<h4>{_inline(block[4:])}</h4>")
        elif block.startswith("## "):
            out.append(f"<h3>{_inline(block[3:])}</h3>")
        elif block.startswith("# "):
            out.append(f"<h2>{_inline(block[2:])}</h2>")
        elif re.match(r"^[-*] ", block):
            items = "".join(
                f"<li>{_inline(line[2:])}</li>"
                for line in block.splitlines() if re.match(r"^[-*] ", line)
            )
            out.append(f"<ul>{items}</ul>")
        else:
            out.append(f"<p>{_inline(block)}</p>")
    return "\n".join(out)
