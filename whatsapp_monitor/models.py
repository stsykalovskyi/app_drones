from django.db import models


class OutgoingMessage(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Очікує'
        SENDING = 'sending', 'Відправляється'
        SENT    = 'sent',    'Відправлено'
        FAILED  = 'failed',  'Помилка'

    group_name   = models.CharField(max_length=255)
    message_text = models.TextField()
    status       = models.CharField(
        max_length=10, choices=Status.choices,
        default=Status.PENDING, db_index=True,
    )
    created_at   = models.DateTimeField(auto_now_add=True)
    sent_at      = models.DateTimeField(null=True, blank=True)
    error        = models.TextField(blank=True)
    retry_count  = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Вихідне повідомлення'
        verbose_name_plural = 'Вихідні повідомлення'

    def __str__(self):
        return f"[{self.status}] {self.group_name}: {self.message_text[:60]}"
