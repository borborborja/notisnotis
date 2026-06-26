from django.urls import path

from . import views

app_name = "podcasts"

urlpatterns = [
    path("ep/<int:pk>/progress/", views.progress, name="progress"),
    path("ep/<int:pk>/played/", views.played, name="played"),
]
