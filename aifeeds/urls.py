from django.urls import path

from . import views

app_name = "aifeeds"

urlpatterns = [
    path("", views.feed_list, name="list"),
    path("<int:pk>/", views.feed_detail, name="detail"),
    path("<int:pk>/search/", views.search_now, name="search"),
    path("<int:pk>/settings/", views.feed_settings, name="settings"),
    path("<int:pk>/delete/", views.feed_delete, name="delete"),
    path("candidate/<int:pk>/decide/", views.candidate_decide, name="decide"),
]
