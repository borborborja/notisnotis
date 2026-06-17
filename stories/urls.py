from django.urls import path

from . import views

app_name = "stories"

urlpatterns = [
    path("", views.home, name="home"),
    path("story/<int:pk>/", views.story_detail, name="detail"),
    path("story/<int:pk>/reading/", views.story_reading, name="reading"),
]
