from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('equipment_accounting', '0041_alter_uavinstance_role'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='uavmovement',
            index=models.Index(fields=['uav', '-created_at'], name='uavmove_uav_created_idx'),
        ),
        migrations.AddIndex(
            model_name='uavmovement',
            index=models.Index(fields=['to_location'], name='uavmove_to_loc_idx'),
        ),
        migrations.AddIndex(
            model_name='component',
            index=models.Index(fields=['status'], name='component_status_idx'),
        ),
    ]
