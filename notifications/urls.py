from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("push/key/", views.push_key, name="push_key"),
    path("push/subscribe/", views.push_subscribe, name="push_subscribe"),
    path("push/unsubscribe/", views.push_unsubscribe, name="push_unsubscribe"),
]
