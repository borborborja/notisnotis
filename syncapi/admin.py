from django.contrib import admin

from .models import SyncCredential


@admin.register(SyncCredential)
class SyncCredentialAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at")
