from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import TemplateView

from accounts import views as account_views
from accounts import twofa as twofa_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("sw.js", TemplateView.as_view(template_name="sw.js", content_type="application/javascript"), name="sw"),
    path("accounts/login/", auth_views.LoginView.as_view(template_name="accounts/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/register/", account_views.register, name="register"),
    path("accounts/2fa/setup/", twofa_views.setup, name="twofa_setup"),
    path("accounts/2fa/verify/", twofa_views.verify, name="twofa_verify"),
    path("accounts/2fa/disable/", twofa_views.disable, name="twofa_disable"),
    path("accounts/2fa/recovery/", twofa_views.regenerate_recovery, name="twofa_recovery"),
    path("accounts/settings/ai/models/", account_views.ai_models, name="ai_models"),
    path("accounts/settings/", account_views.settings_view, name="account_settings"),
    path("accounts/export.json", account_views.export_data, name="account_export"),
    path("accounts/import/", account_views.import_data, name="account_import"),
    path("accounts/settings/<str:tab>/", account_views.settings_view, name="account_settings_tab"),
    path("api/", include("syncapi.urls")),
    path("notifications/", include("notifications.urls")),
    path("feeds/", include("feeds.urls")),
    path("aifeeds/", include("aifeeds.urls")),
    path("articles/", include("articles.urls")),
    path("", include("stories.urls")),
]
