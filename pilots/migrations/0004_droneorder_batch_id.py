import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pilots', '0003_strikereport_crew'),
    ]

    operations = [
        migrations.AddField(
            model_name='droneorder',
            name='batch_id',
            field=models.UUIDField(blank=True, db_index=True, null=True, verbose_name='Партія'),
        ),
    ]
