"""Map old Component statuses to the new set."""

from django.db import migrations


def migrate_statuses(apps, schema_editor):
    Component = apps.get_model('equipment_accounting', 'Component')
    mapping = {
        'available': 'in_use',
        'retired': 'disassembled',
        'damaged': 'damaged',
    }
    for old, new in mapping.items():
        Component.objects.filter(status=old).update(status=new)


class Migration(migrations.Migration):

    dependencies = [
        ('equipment_accounting', '0007_remove_uavinstance_kit_status_alter_component_status'),
    ]

    operations = [
        migrations.RunPython(migrate_statuses, migrations.RunPython.noop),
    ]
