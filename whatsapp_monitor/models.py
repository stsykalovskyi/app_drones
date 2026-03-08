from django.db import models


class StrikeReport(models.Model):
    RESULT_DESTROYED = 'destroyed'
    RESULT_DAMAGED   = 'damaged'
    RESULT_MISSED    = 'missed'
    RESULT_UNKNOWN   = 'unknown'

    RESULT_CHOICES = [
        (RESULT_DESTROYED, 'Знищено'),
        (RESULT_DAMAGED,   'Пошкоджено'),
        (RESULT_MISSED,    'Не вражено'),
        (RESULT_UNKNOWN,   'Невідомо'),
    ]

    # raw data
    whatsapp_msg_id = models.CharField(max_length=120, unique=True, db_index=True)
    raw_text        = models.TextField(verbose_name='Сирий текст')
    sender_name     = models.CharField(max_length=200, blank=True, verbose_name='Відправник')
    group_name      = models.CharField(max_length=200, blank=True, verbose_name='Група')
    received_at     = models.DateTimeField(verbose_name='Час отримання')
    created_at      = models.DateTimeField(auto_now_add=True)

    # parsed fields
    pozyvnyi    = models.CharField(max_length=100, blank=True, verbose_name='Поз')
    crew        = models.CharField(max_length=100, blank=True, verbose_name='ЕК')
    zasib       = models.CharField(max_length=200, blank=True, verbose_name='Засіб')
    bk          = models.CharField(max_length=200, blank=True, verbose_name='БК')
    target      = models.CharField(max_length=200, blank=True, verbose_name='Ціль')
    coordinates = models.CharField(max_length=100, blank=True, verbose_name='Координати')
    result      = models.CharField(
        max_length=20, blank=True,
        choices=RESULT_CHOICES, verbose_name='Результат',
    )
    parsed_ok = models.BooleanField(default=False, verbose_name='Розпізнано')

    class Meta:
        verbose_name          = 'Звіт ураження'
        verbose_name_plural   = 'Звіти уражень'
        ordering              = ['-received_at']
        indexes = [
            models.Index(fields=['-received_at']),
            models.Index(fields=['result']),
            models.Index(fields=['pozyvnyi']),
        ]

    def __str__(self):
        return f"{self.received_at:%d.%m.%Y %H:%M} | {self.pozyvnyi} | {self.target} | {self.get_result_display()}"
