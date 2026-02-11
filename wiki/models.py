from django.db import models
from django.utils.text import slugify


class TimeStampedModel(models.Model):
    """Reusable timestamp mixin."""

    created_at = models.DateTimeField("Створено", auto_now_add=True)
    updated_at = models.DateTimeField("Оновлено", auto_now=True)

    class Meta:
        abstract = True


class Topic(TimeStampedModel):
    """High-level grouping for wiki content."""

    name = models.CharField("Назва", max_length=120, unique=True)
    slug = models.SlugField("Slug", max_length=140, unique=True, blank=True)
    description = models.TextField("Опис", blank=True)
    icon = models.CharField(
        "Іконка",
        max_length=60,
        blank=True,
        help_text="Короткий маркер (емодзі/текст) для швидкого перегляду.",
    )

    class Meta:
        verbose_name = "Тема"
        verbose_name_plural = "Теми"
        ordering = ("name",)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Article(TimeStampedModel):
    """Primary knowledge entry."""

    topic = models.ForeignKey(
        Topic,
        related_name="articles",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Тема",
    )
    title = models.CharField("Заголовок", max_length=180, unique=True)
    slug = models.SlugField("Slug", max_length=200, unique=True, blank=True)
    summary = models.TextField(
        "Короткий опис",
        help_text="Один абзац для відображення у списку.",
        blank=True,
    )
    tags = models.CharField(
        "Теги",
        max_length=200,
        blank=True,
        help_text="Ключові слова через кому для пошуку та фільтрації.",
    )
    body = models.TextField("Текст статті")
    hero_image_url = models.URLField("URL зображення", blank=True)
    references = models.TextField(
        "Посилання",
        blank=True,
        help_text="Одне посилання на рядок (URL, інструкції тощо).",
    )

    class Meta:
        verbose_name = "Стаття"
        verbose_name_plural = "Статті"
        ordering = ("title",)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def tag_list(self):
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(",") if tag.strip()]
