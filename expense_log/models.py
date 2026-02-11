from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


def expense_receipt_path(instance, filename):
    """Upload receipts to expense_receipts/<year>/<month>/<filename>."""
    date = instance.date or timezone.now().date()
    return f"expense_receipts/{date.year}/{date.month:02d}/{filename}"


class Expense(models.Model):
    """Single financial expense record."""

    date = models.DateField("Дата", default=timezone.now)
    amount = models.DecimalField("Сума", max_digits=12, decimal_places=2)
    description = models.TextField("На що витрачено")
    receipt = models.FileField(
        "Квитанція",
        upload_to=expense_receipt_path,
        max_length=500,
        blank=True,
        help_text="Фото або документ квитанції.",
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="expenses",
        verbose_name="Створив",
    )
    notes = models.TextField("Примітки", blank=True)

    created_at = models.DateTimeField("Створено", auto_now_add=True)
    updated_at = models.DateTimeField("Оновлено", auto_now=True)

    class Meta:
        verbose_name = "Витрата"
        verbose_name_plural = "Витрати"
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.date} — {self.amount} грн — {self.description}"
