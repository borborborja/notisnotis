from django.contrib import admin

from .models import Story, StoryArticle


class StoryArticleInline(admin.TabularInline):
    model = StoryArticle
    extra = 0
    raw_id_fields = ("article",)


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = ("headline", "user", "is_blindspot", "blindspot_side", "analyzed_at", "dirty")
    list_filter = ("is_blindspot", "dirty", "user")
    search_fields = ("headline",)
    inlines = [StoryArticleInline]
    readonly_fields = ("centroid", "bias_distribution", "perspectives")
