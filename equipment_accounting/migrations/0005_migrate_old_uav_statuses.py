"""Map old UAVInstance statuses to the new set."""

from django.db import migrations


def migrate_statuses(apps, schema_editor):
    UAVInstance = apps.get_model('equipment_accounting', 'UAVInstance')
    mapping = {
        'operational': 'ready',
        'maintenance': 'repair',
        'damaged': 'repair',
        'retired': 'deferred',
        'destroyed': 'deferred',
        'available': 'ready',
        'handed_over': 'ready',
        'verified': 'ready',
    }
    for old, new in mapping.items():
        UAVInstance.objects.filter(status=old).update(status=new)


class Migration(migrations.Migration):

    dependencies = [
        ('equipment_accounting', '0004_alter_uavinstance_status'),
    ]

    operations = [
        migrations.RunPython(migrate_statuses, migrations.RunPython.noop),
    ]
