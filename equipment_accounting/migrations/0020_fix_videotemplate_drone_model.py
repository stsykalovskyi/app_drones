"""
Data migration: populate VideoTemplate.drone_model from the linked OpticalDroneType
for templates that currently have drone_model=NULL but are referenced by drone types.
Also regenerates the template name to include the drone model.
"""
from django.db import migrations


def fix_videotemplate_drone_models(apps, schema_editor):
    VideoTemplate = apps.get_model('equipment_accounting', 'VideoTemplate')
    OpticalDroneType = apps.get_model('equipment_accounting', 'OpticalDroneType')

    # Find all VideoTemplates with null drone_model that are used by exactly one drone model
    for vt in VideoTemplate.objects.filter(drone_model__isnull=True):
        # Get distinct drone models used by OpticalDroneTypes linked to this template
        drone_model_ids = (
            OpticalDroneType.objects
            .filter(video_template=vt)
            .values_list('model_id', flat=True)
            .distinct()
        )
        if len(drone_model_ids) == 1:
            vt.drone_model_id = drone_model_ids[0]
            # Rebuild name in the same format as VideoTemplateForm._build_name
            signal = "аналог" if vt.is_analog else "цифра"
            # Get drone model __str__ equivalent
            dm = vt.drone_model
            dm_str = f"{dm.manufacturer.name} {dm.name}" if hasattr(dm, 'manufacturer') else str(dm)
            vt.name = f"{dm_str} {signal} {vt.max_distance}км"
            vt.save(update_fields=['drone_model', 'name'])


def reverse_fix(apps, schema_editor):
    pass  # Not reversible — would need original names stored somewhere


class Migration(migrations.Migration):

    dependencies = [
        ('equipment_accounting', '0019_add_component_given_status'),
    ]

    operations = [
        migrations.RunPython(fix_videotemplate_drone_models, reverse_fix),
    ]
