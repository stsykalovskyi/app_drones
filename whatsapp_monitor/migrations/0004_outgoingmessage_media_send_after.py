from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp_monitor', '0003_delete_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='outgoingmessage',
            name='media_path',
            field=models.CharField(blank=True, max_length=500,
                                   verbose_name='Шлях до файлу (відео/фото)'),
        ),
        migrations.AddField(
            model_name='outgoingmessage',
            name='send_after',
            field=models.DateTimeField(blank=True, db_index=True, null=True,
                                       verbose_name='Надіслати не раніше'),
        ),
        migrations.AlterField(
            model_name='outgoingmessage',
            name='message_text',
            field=models.TextField(blank=True),
        ),
    ]
