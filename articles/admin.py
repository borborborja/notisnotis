from django.contrib import admin

from .models import Article


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "source", "published_at", "is_read", "is_saved", "enriched_at")
    list_filter = ("source", "is_read", "is_saved")
    search_fields = ("title", "url")
    readonly_fields = ("embedding", "claims")
