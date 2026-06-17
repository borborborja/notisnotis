from django.urls import path

from . import views

app_name = "stories"

urlpatterns = [
    path("", views.home, name="home"),
    path("story/<int:pk>/", views.story_detail, name="detail"),
    path("story/<int:pk>/reading/", views.story_reading, name="reading"),
    path("diet/", views.bias_diet, name="bias_diet"),
    path("trending/", views.trending, name="trending"),
    path("compare/", views.compare_sources, name="compare"),
    path("topics/", views.topic_list, name="topic_list"),
    path("topics/<int:pk>/delete/", views.topic_delete, name="topic_delete"),
]
