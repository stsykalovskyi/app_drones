from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp_monitor', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='OutgoingMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('group_name', models.CharField(max_length=255)),
                ('message_text', models.TextField()),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Очікує'),
                        ('sending', 'Відправляється'),
                        ('sent', 'Відправлено'),
                        ('failed', 'Помилка'),
                    ],
                    db_index=True,
                    default='pending',
                    max_length=10,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('error', models.TextField(blank=True)),
                ('retry_count', models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                'verbose_name': 'Вихідне повідомлення',
                'verbose_name_plural': 'Вихідні повідомлення',
                'ordering': ['created_at'],
            },
        ),
    ]
