"""Construye y envía el digest por email usando el SMTP resuelto por usuario."""
from __future__ import annotations

from datetime import timedelta

from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string
from django.utils import timezone

from articles.models import Article
from stories.models import Story

from .config import DIGEST, digest_prefs, smtp_settings


def _connection(smtp):
    return get_connection(
        backend="django.core.mail.backends.smtp.EmailBackend",
        host=smtp["smtp_host"], port=smtp["smtp_port"],
        username=smtp["smtp_user"] or None, password=smtp["smtp_password"] or None,
        use_tls=smtp["smtp_tls"],
    )


def build_content(user, since):
    arts = (
        Article.objects.filter(feed__user=user, is_read=False, fetched_at__gte=since)
        .select_related("source")
        .order_by("-published_at")[:20]
    )
    blindspots = Story.objects.filter(user=user, is_blindspot=True, last_updated__gte=since)[:8]
    return list(arts), list(blindspots)


def send_digest_to(user, frequency, *, connection=None, dry_run=False):
    """Devuelve 'sent' | 'skipped:<motivo>'."""
    if not DIGEST.enabled():
        return "skipped:disabled"
    prefs = digest_prefs(user)
    if not prefs["optin"] or prefs["frequency"] != frequency:
        return "skipped:not_optin"
    smtp = smtp_settings(user)
    if not smtp["smtp_host"] or not smtp["smtp_from"]:
        return "skipped:no_smtp"
    to = prefs["email"]
    if not to:
        return "skipped:no_email"

    days = 7 if frequency == "weekly" else 1
    since = timezone.now() - timedelta(days=days)
    articles, blindspots = build_content(user, since)
    if not articles and not blindspots:
        return "skipped:empty"

    ctx = {"user": user, "articles": articles, "blindspots": prefs["include_blindspots"] and blindspots or [],
           "frequency": frequency, "days": days}
    text = render_to_string("notifications/digest.txt", ctx)
    html = render_to_string("notifications/digest.html", ctx)
    if dry_run:
        return "sent"

    conn = connection or _connection(smtp)
    msg = EmailMultiAlternatives(
        subject=f"NotisNotis · resumen {'semanal' if days == 7 else 'diario'}",
        body=text, from_email=smtp["smtp_from"], to=[to], connection=conn,
    )
    msg.attach_alternative(html, "text/html")
    msg.send()
    return "sent"
