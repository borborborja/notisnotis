from django.contrib import admin

from .models import UserEntitlements


@admin.register(UserEntitlements)
class UserEntitlementsAdmin(admin.ModelAdmin):
    list_display = ("user", "tier", "beta_access", "tier_expires", "updated_at")
    list_filter = ("tier", "beta_access")
    search_fields = ("user__username",)
