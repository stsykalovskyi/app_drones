from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class StrikeReport(models.Model):
    """Звіт пілота про результат удару БПЛА."""

    pilot = models.ForeignKey(
        User, on_delete=models.PROTECT,
        related_name='strike_reports', verbose_name="Пілот"
    )
    strike_date = models.DateField(verbose_name="Дата удару")
    target_description = models.CharField(max_length=300, verbose_name="Ціль")
    result_description = models.TextField(verbose_name="Результат")
    drone_used = models.CharField(max_length=150, blank=True, verbose_name="Дрон (опис)")
    location_description = models.CharField(max_length=300, blank=True, verbose_name="Місце")
    photo = models.ImageField(
        upload_to='strikes/%Y/%m/', null=True, blank=True,
        verbose_name="Фото"
    )
    reported_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата звіту")

    class Meta:
        verbose_name = "Звіт про удар"
        verbose_name_plural = "Звіти про удари"
        ordering = ['-reported_at']

    def __str__(self):
        return f"{self.pilot} — {self.strike_date}"


class DroneOrder(models.Model):
    """Замовлення дронів пілотом у майстерні."""

    STATUS_CHOICES = [
        ('pending', 'Очікує'),
        ('in_progress', 'В роботі'),
        ('ready', 'Готово'),
        ('delivered', 'Видано'),
        ('cancelled', 'Скасовано'),
    ]

    STATUS_COLORS = {
        'pending': 'warning',
        'in_progress': 'info',
        'ready': 'success',
        'delivered': 'muted',
        'cancelled': 'error',
    }

    pilot = models.ForeignKey(
        User, on_delete=models.PROTECT,
        related_name='drone_orders', verbose_name="Пілот"
    )
    # Polymorphic reference to FPVDroneType or OpticalDroneType
    content_type = models.ForeignKey(
        ContentType, on_delete=models.PROTECT,
        null=True, blank=True, verbose_name="Тип БПЛА (тип)"
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    drone_type_obj = GenericForeignKey('content_type', 'object_id')

    quantity = models.PositiveIntegerField(default=1, verbose_name="Кількість")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES,
        default='pending', verbose_name="Статус"
    )
    notes = models.TextField(blank=True, verbose_name="Примітки пілота")
    handled_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='handled_drone_orders', verbose_name="Обробляє"
    )
    master_notes = models.TextField(blank=True, verbose_name="Примітки майстра")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Замовлено")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Оновлено")

    class Meta:
        verbose_name = "Замовлення дрона"
        verbose_name_plural = "Замовлення дронів"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.pilot} — {self.drone_type_name} x{self.quantity}"

    @property
    def drone_type_name(self):
        obj = self.drone_type_obj
        return str(obj) if obj else '—'

    @property
    def status_color(self):
        return self.STATUS_COLORS.get(self.status, 'info')
