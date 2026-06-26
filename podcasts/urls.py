from django.urls import path

from . import views

app_name = "podcasts"

urlpatterns = [
    path("", views.home, name="home"),
    path("up-next/", views.up_next, name="up_next"),
    path("downloads/", views.downloads, name="downloads"),
    path("list/<str:kind>/", views.filtered, name="filtered"),
    path("<int:pk>/", views.podcast_detail, name="detail"),
    path("<int:pk>/mark-played/", views.mark_feed_played, name="mark_feed_played"),
    path("queue/clear/", views.queue_clear, name="queue_clear"),
    path("ep/<int:pk>/progress/", views.progress, name="progress"),
    path("ep/<int:pk>/played/", views.played, name="played"),
    path("ep/<int:pk>/queue/", views.queue_add, name="queue_add"),
    path("ep/<int:pk>/unqueue/", views.queue_remove, name="queue_remove"),
    path("queue/reorder/", views.queue_reorder, name="queue_reorder"),
    path("import/antennapod/", views.import_antennapod, name="import_antennapod"),
]
