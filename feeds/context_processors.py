"""Datos del sidebar (categorías, feeds, contadores) para todas las páginas del shell."""
from django.db.models import Count, Q

from articles.models import Article, Tag
from feeds.models import Category, Feed
from stories.models import Story


def sidebar(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}

    feeds = (
        Feed.objects.filter(user=user, ai_feed__isnull=True, kind="rss")  # IA y audio en su sección
        .select_related("source", "category")
        .annotate(unread=Count("articles", filter=Q(articles__is_read=False)))
    )

    # Agrupa feeds por categoría (None = "Sin categoría").
    by_cat = {}
    for feed in feeds:
        by_cat.setdefault(feed.category_id, []).append(feed)

    categories = []
    for cat in Category.objects.filter(user=user):
        cat_feeds = by_cat.get(cat.id, [])
        categories.append(
            {"id": cat.id, "name": cat.name, "feeds": cat_feeds,
             "unread": sum(f.unread for f in cat_feeds)}
        )
    uncategorized = by_cat.get(None, [])

    from articles.ai_actions import reading_prefs

    tags = list(Tag.objects.filter(user=user).annotate(n=Count("articles")).filter(n__gt=0))

    # Fuentes IA (feeds creados con IA): su feed sintético para leer + propuestas pendientes.
    from aifeeds.models import AIFeed

    aifeeds = []
    for ai in (AIFeed.objects.filter(user=user)
               .annotate(unread=Count("feed__articles", filter=Q(feed__articles__is_read=False)),
                         pending=Count("candidates", filter=Q(candidates__status="pending")))):
        aifeeds.append({"id": ai.id, "name": ai.name, "feed_id": ai.feed_id,
                        "unread": ai.unread, "pending": ai.pending})

    # Fuentes audio (podcasts + canales de YouTube).
    audio_feeds = list(
        Feed.objects.filter(user=user, kind__in=["podcast", "youtube"])
        .select_related("source")
        .annotate(unread=Count("articles", filter=Q(articles__is_read=False)))
    )

    return {
        "sidebar_categories": categories,
        "sidebar_uncategorized": uncategorized,
        "sidebar_aifeeds": aifeeds,
        "sidebar_audio": audio_feeds,
        "sidebar_tags": tags,
        "reading_ui": reading_prefs(user),
        "sidebar_counts": {
            "unread": Article.objects.filter(feed__user=user, is_read=False).count(),
            "saved": Article.objects.filter(feed__user=user, is_saved=True).count(),
            "stories": Story.objects.filter(user=user).count(),
            "blindspots": Story.objects.filter(user=user, is_blindspot=True).count(),
        },
    }
