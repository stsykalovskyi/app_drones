from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Article, Topic


@admin.register(Topic)
class TopicAdmin(ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}
    list_display = ("name", "icon", "description")
    search_fields = ("name", "description")


@admin.register(Article)
class ArticleAdmin(ModelAdmin):
    prepopulated_fields = {"slug": ("title",)}
    list_display = ("title", "topic", "updated_at")
    list_filter = ("topic",)
    search_fields = ("title", "summary", "body", "tags")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("title", "slug", "topic", "tags")}),
        ("Огляд", {"fields": ("summary", "hero_image_url")}),
        ("Контент", {"fields": ("body", "references")}),
        ("Мітки часу", {"fields": ("created_at", "updated_at")}),
    )
