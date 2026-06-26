from django.urls import path

from . import actions, curation, management, meta, podcasts, reader, sync

app_name = "api"

urlpatterns = [
    # API-1 · auth + meta + delta-sync
    path("auth/token", meta.auth_token, name="auth_token"),
    path("me", meta.me, name="me"),
    path("modules", meta.modules, name="modules"),
    path("sync", sync.sync, name="sync"),

    # API-2 · lector RSS + estado
    path("feeds", reader.feeds, name="feeds"),
    path("categories", reader.categories, name="categories"),
    path("tags", reader.tags, name="tags"),
    path("articles", reader.articles, name="articles"),
    path("articles/state", reader.articles_state, name="articles_state"),
    path("articles/<int:pk>", reader.article_detail, name="article_detail"),
    path("articles/<int:pk>/state", reader.article_state, name="article_state"),
    path("articles/<int:pk>/tags", reader.article_tags, name="article_tags"),

    # API-3 · podcasts
    path("podcasts", podcasts.podcasts, name="podcasts"),
    path("podcasts/<int:pk>", podcasts.podcast_detail, name="podcast_detail"),
    path("podcasts/<int:pk>/settings", podcasts.podcast_settings, name="podcast_settings"),
    path("episodes", podcasts.episodes, name="episodes"),
    path("episodes/<int:pk>/progress", podcasts.progress, name="episode_progress"),
    path("episodes/<int:pk>/played", podcasts.played, name="episode_played"),
    path("queue", podcasts.queue, name="queue"),
    path("queue/reorder", podcasts.queue_reorder, name="queue_reorder"),
    path("queue/<int:pk>", podcasts.queue_remove, name="queue_remove"),

    # API-4 · curación IA
    path("stories", curation.stories, name="stories"),
    path("stories/<int:pk>", curation.story_detail, name="story_detail"),
    path("trending", curation.trending, name="trending"),
    path("trending/countries", curation.trending_countries, name="trending_countries"),
    path("trending/<int:pk>", curation.trending_detail, name="trending_detail"),
    path("aifeeds", curation.aifeeds, name="aifeeds"),
    path("aifeeds/<int:pk>", curation.aifeed_detail, name="aifeed_detail"),
    path("aifeeds/<int:pk>/search", curation.aifeed_search, name="aifeed_search"),
    path("aifeeds/candidates/<int:pk>", curation.candidate_decide, name="candidate_decide"),
    path("topics", curation.topics, name="topics"),
    path("topics/<int:pk>", curation.topic_delete, name="topic_delete"),
    path("articles/<int:pk>/related", curation.related, name="related"),

    # API-5 · gestión + IA on-demand
    path("subscribe", management.subscribe, name="subscribe"),
    path("feeds/<int:pk>", management.feed_detail, name="feed_manage"),
    path("manage/categories", management.categories, name="categories_manage"),
    path("manage/categories/<int:pk>", management.category_detail, name="category_manage"),
    path("opml/import", management.opml_import, name="opml_import"),
    path("opml/export", management.opml_export, name="opml_export"),
    path("articles/<int:pk>/summarize", actions.summarize, name="summarize"),
    path("articles/<int:pk>/translate", actions.translate, name="translate"),
    path("articles/<int:pk>/context", actions.context, name="context"),
    path("articles/<int:pk>/chat", actions.chat, name="chat"),
]
