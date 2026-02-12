from django.contrib.auth.models import User
from django.db import models
from django.utils.text import slugify

from wiki.models import TimeStampedModel


class Category(TimeStampedModel):
    """Flat category for documentation pages."""

    name = models.CharField("Назва", max_length=120, unique=True)
    slug = models.SlugField("Slug", max_length=140, unique=True, blank=True)

    class Meta:
        verbose_name = "Категорія"
        verbose_name_plural = "Категорії"
        ordering = ("name",)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Page(TimeStampedModel):
    """Documentation page with Markdown body."""

    category = models.ForeignKey(
        Category,
        related_name="pages",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Категорія",
    )
    title = models.CharField("Заголовок", max_length=200, unique=True)
    slug = models.SlugField("Slug", max_length=220, unique=True, blank=True)
    body = models.TextField("Зміст (Markdown)")
    author = models.ForeignKey(
        User,
        related_name="documentation_pages",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Автор",
    )

    class Meta:
        verbose_name = "Сторінка"
        verbose_name_plural = "Сторінки"
        ordering = ("-updated_at",)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class Comment(TimeStampedModel):
    """Correction / comment on a documentation page."""

    page = models.ForeignKey(
        Page,
        related_name="comments",
        on_delete=models.CASCADE,
        verbose_name="Сторінка",
    )
    author = models.ForeignKey(
        User,
        related_name="documentation_comments",
        on_delete=models.CASCADE,
        verbose_name="Автор",
    )
    body = models.TextField("Коментар")

    class Meta:
        verbose_name = "Коментар"
        verbose_name_plural = "Коментарі"
        ordering = ("created_at",)

    def __str__(self):
        return f"{self.author} — {self.page} ({self.created_at:%Y-%m-%d})"
