from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp_monitor', '0002_outgoing_message'),
    ]

    operations = [
        migrations.DeleteModel(name='StrikeReport'),
    ]
