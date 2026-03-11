from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Category, Comment, Page, Question


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


@admin.register(Question)
class QuestionAdmin(ModelAdmin):
    list_display = ("user", "question_text_short", "is_answered", "created_at")
    list_filter = ("is_answered",)
    search_fields = ("question_text", "answer_text", "user__username")
    readonly_fields = ("created_at", "updated_at")

    def question_text_short(self, obj):
        return obj.question_text[:80]
    question_text_short.short_description = "Питання"
