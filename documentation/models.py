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


class KnowledgeDocument(TimeStampedModel):
    """Uploaded document for the knowledge base (PDF, TXT, MD)."""

    STATUS_PENDING    = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_READY      = 'ready'
    STATUS_ERROR      = 'error'
    STATUS_CHOICES = [
        (STATUS_PENDING,    'Очікує обробки'),
        (STATUS_PROCESSING, 'Обробляється'),
        (STATUS_READY,      'Готово'),
        (STATUS_ERROR,      'Помилка'),
    ]
    STATUS_COLORS = {
        STATUS_PENDING:    'secondary',
        STATUS_PROCESSING: 'warning',
        STATUS_READY:      'success',
        STATUS_ERROR:      'danger',
    }

    title          = models.CharField("Назва", max_length=200)
    file           = models.FileField("Файл", upload_to='knowledge_docs/')
    file_size      = models.PositiveBigIntegerField("Розмір (байт)", null=True, blank=True)
    page_count     = models.PositiveIntegerField("Сторінок", null=True, blank=True)
    extracted_text = models.TextField("Витягнутий текст", blank=True)
    status         = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    error_message  = models.TextField("Помилка", blank=True)
    is_active      = models.BooleanField("Активний", default=True, db_index=True)

    class Meta:
        verbose_name = "Документ бази знань"
        verbose_name_plural = "Документи бази знань"
        ordering = ('-created_at',)

    def __str__(self):
        return self.title

    @property
    def status_color(self):
        return self.STATUS_COLORS.get(self.status, 'secondary')

    @property
    def filename(self):
        return self.file.name.split('/')[-1] if self.file else ''

    @property
    def file_size_human(self):
        if not self.file_size:
            return '—'
        for unit in ('Б', 'КБ', 'МБ', 'ГБ'):
            if self.file_size < 1024:
                return f'{self.file_size:.0f} {unit}'
            self.file_size /= 1024
        return f'{self.file_size:.1f} ГБ'


class Question(TimeStampedModel):
    """Питання пілота до бази знань — відповідь надає Gemini."""

    user = models.ForeignKey(
        User,
        related_name='knowledge_questions',
        on_delete=models.CASCADE,
        verbose_name="Користувач",
    )
    question_text = models.TextField("Питання")
    answer_text = models.TextField("Відповідь", blank=True)
    is_answered = models.BooleanField("Відповідь отримано", default=False)

    class Meta:
        verbose_name = "Питання"
        verbose_name_plural = "Питання"
        ordering = ('-created_at',)

    def __str__(self):
        return f"{self.user} — {self.question_text[:60]}"
