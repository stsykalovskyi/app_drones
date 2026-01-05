from django.contrib import admin

from .models import Article, Topic


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}
    list_display = ("name", "icon", "description")
    search_fields = ("name", "description")


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("title",)}
    list_display = ("title", "topic", "updated_at")
    list_filter = ("topic",)
    search_fields = ("title", "summary", "body", "tags")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("title", "slug", "topic", "tags")}),
        ("Overview", {"fields": ("summary", "hero_image_url")}),
        ("Content", {"fields": ("body", "references")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
