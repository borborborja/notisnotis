from django.contrib import admin

from .models import ApiToken, UserConfig


@admin.register(UserConfig)
class UserConfigAdmin(admin.ModelAdmin):
    list_display = ("user",)


@admin.register(ApiToken)
class ApiTokenAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "created_at", "last_used")
    list_filter = ("user",)
