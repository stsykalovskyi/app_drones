from django.db import models
from django.utils.text import slugify


class TimeStampedModel(models.Model):
    """Reusable timestamp mixin."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Topic(TimeStampedModel):
    """High-level grouping for wiki content."""

    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(
        max_length=60,
        blank=True,
        help_text="Optional short label (emoji/text) for quick scanning.",
    )

    class Meta:
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
        Topic, related_name="articles", on_delete=models.SET_NULL, null=True, blank=True
    )
    title = models.CharField(max_length=180, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    summary = models.TextField(
        help_text="Single paragraph overview used in listings.",
        blank=True,
    )
    tags = models.CharField(
        max_length=200,
        blank=True,
        help_text="Comma separated keywords for search and quick filtering.",
    )
    body = models.TextField()
    hero_image_url = models.URLField(blank=True)
    references = models.TextField(
        blank=True, help_text="One reference per line (e.g. URLs, manuals)."
    )

    class Meta:
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

# Create your models here.
