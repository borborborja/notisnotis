from django.contrib import admin

from .models import Category, Feed, Source


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "position")
    list_filter = ("user",)


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ("name", "domain", "bias", "factuality", "bias_source")
    list_filter = ("bias", "bias_source")
    search_fields = ("name", "domain")
    list_editable = ("bias",)

    def save_model(self, request, obj, form, change):
        if "bias" in form.changed_data:
            obj.bias_source = "manual"
        super().save_model(request, obj, form, change)


@admin.register(Feed)
class FeedAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "source", "enabled", "last_fetched")
    list_filter = ("enabled", "user")
    search_fields = ("title", "url")
