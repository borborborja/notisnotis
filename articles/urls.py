from django.urls import path

from . import views

app_name = "articles"

urlpatterns = [
    path("", views.article_list, name="list"),
    path("mark-all-read/", views.mark_all_read, name="mark_all_read"),
    path("pref/", views.set_reading_pref, name="set_reading_pref"),
    path("<int:pk>/", views.article_detail, name="detail"),
    path("<int:pk>/reading/", views.reading_pane, name="reading"),
    path("<int:pk>/related/", views.related_panel, name="related"),
    path("<int:pk>/transcribe/", views.request_transcribe, name="transcribe"),
    path("<int:pk>/fulltext/", views.fetch_fulltext, name="fetch_fulltext"),
    path("<int:pk>/save/", views.toggle_saved, name="toggle_saved"),
    path("<int:pk>/read/", views.mark_read, name="mark_read"),
    path("<int:pk>/seen/", views.mark_seen, name="mark_seen"),
    path("<int:pk>/translate/", views.translate, name="translate"),
    path("<int:pk>/summarize/", views.summarize, name="summarize"),
    path("<int:pk>/chat/", views.chat_panel, name="chat"),
    path("<int:pk>/chat/send/", views.chat_message, name="chat_send"),
    path("<int:pk>/tag/", views.tag_add, name="tag_add"),
    path("<int:pk>/untag/", views.tag_remove, name="tag_remove"),
    path("<int:pk>/export.md", views.export_markdown, name="export_markdown"),
    path("<int:pk>/webhook/", views.send_webhook, name="send_webhook"),
]
