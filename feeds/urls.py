from django.urls import path

from . import views

app_name = "feeds"

urlpatterns = [
    path("", views.feed_list, name="feed_list"),
    path("opml/", views.upload_opml, name="upload_opml"),
    path("opml/export/", views.export_opml, name="export_opml"),
    path("refresh/", views.refresh, name="refresh"),
    path("subscribe/", views.subscribe, name="subscribe"),
    path("rules/", views.rule_list, name="rule_list"),
    path("rules/<int:pk>/delete/", views.rule_delete, name="rule_delete"),
    path("rules/<int:pk>/toggle/", views.rule_toggle, name="rule_toggle"),
    path("categories/create/", views.category_create, name="category_create"),
    path("categories/reorder/", views.category_reorder, name="category_reorder"),
    path("categories/<int:pk>/rename/", views.category_rename, name="category_rename"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
    path("<int:pk>/set-category/", views.feed_set_category, name="feed_set_category"),
    path("<int:pk>/edit/", views.feed_edit, name="feed_edit"),
    path("<int:pk>/reactivate/", views.reactivate_feed, name="reactivate_feed"),
    path("<int:pk>/toggle/", views.toggle_feed, name="toggle_feed"),
    path("<int:pk>/delete/", views.delete_feed, name="delete_feed"),
]
