from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Category, Comment, Page


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Page)
class PageAdmin(ModelAdmin):
    list_display = ("title", "category", "author", "updated_at")
    list_filter = ("category", "author")
    search_fields = ("title", "body")
    prepopulated_fields = {"slug": ("title",)}
    raw_id_fields = ("author",)


@admin.register(Comment)
class CommentAdmin(ModelAdmin):
    list_display = ("page", "author", "created_at")
    list_filter = ("page", "author")
    search_fields = ("body",)
    raw_id_fields = ("page", "author")
