"""Copy control_frequency FK values to control_frequencies M2M."""

from django.db import migrations


def copy_fk_to_m2m(apps, schema_editor):
    for model_name in ('FPVDroneType', 'OpticalDroneType'):
        Model = apps.get_model('equipment_accounting', model_name)
        for obj in Model.objects.filter(control_frequency__isnull=False):
            obj.control_frequencies.add(obj.control_frequency)


class Migration(migrations.Migration):

    dependencies = [
        ('equipment_accounting', '0011_add_control_frequencies_m2m'),
    ]

    operations = [
        migrations.RunPython(copy_fk_to_m2m, migrations.RunPython.noop),
    ]
