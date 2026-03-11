"""
Merge DroneRole into DronePurpose:
  1. Add UAVInstance.role_purpose → FK(DronePurpose)
  2. Data-migrate: set role_purpose = drone type's DronePurpose for every instance
  3. Remove old UAVInstance.role → FK(DroneRole)
  4. Rename role_purpose → role
  5. Delete DroneRole model
"""

import django.db.models.deletion
from django.db import migrations, models


def _migrate_roles_to_purposes(apps, schema_editor):
    UAVInstance = apps.get_model('equipment_accounting', 'UAVInstance')
    FPVDroneType = apps.get_model('equipment_accounting', 'FPVDroneType')
    OpticalDroneType = apps.get_model('equipment_accounting', 'OpticalDroneType')

    # Look up content-type IDs by name (avoids get_for_model issues with historical models)
    ContentType = apps.get_model('contenttypes', 'ContentType')
    try:
        fpv_ct_id = ContentType.objects.get(
            app_label='equipment_accounting', model='fpvdronetype'
        ).pk
    except ContentType.DoesNotExist:
        fpv_ct_id = None
    try:
        opt_ct_id = ContentType.objects.get(
            app_label='equipment_accounting', model='opticaldronetype'
        ).pk
    except ContentType.DoesNotExist:
        opt_ct_id = None

    # Build (content_type_id, object_id) → purpose_id map
    type_purpose = {}
    if fpv_ct_id:
        for row in FPVDroneType.objects.filter(
            purpose_id__isnull=False
        ).values('pk', 'purpose_id'):
            type_purpose[(fpv_ct_id, row['pk'])] = row['purpose_id']
    if opt_ct_id:
        for row in OpticalDroneType.objects.filter(
            purpose_id__isnull=False
        ).values('pk', 'purpose_id'):
            type_purpose[(opt_ct_id, row['pk'])] = row['purpose_id']

    to_update = []
    for uav in UAVInstance.objects.all():
        purpose_id = type_purpose.get((uav.content_type_id, uav.object_id))
        if purpose_id:
            uav.role_purpose_id = purpose_id
            to_update.append(uav)

    if to_update:
        UAVInstance.objects.bulk_update(to_update, ['role_purpose_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('equipment_accounting', '0039_fpvdronetype_photo_opticaldronetype_photo'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        # Step 1: add the new FK field pointing to DronePurpose
        migrations.AddField(
            model_name='uavinstance',
            name='role_purpose',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+',
                to='equipment_accounting.dronepurpose',
                verbose_name='Призначення',
            ),
        ),

        # Step 2: populate it from each UAV's drone type purpose
        migrations.RunPython(_migrate_roles_to_purposes, migrations.RunPython.noop),

        # Step 3: remove old role FK (DroneRole)
        migrations.RemoveField(
            model_name='uavinstance',
            name='role',
        ),

        # Step 4: rename role_purpose → role
        migrations.RenameField(
            model_name='uavinstance',
            old_name='role_purpose',
            new_name='role',
        ),

        # Step 5: delete the DroneRole model
        migrations.DeleteModel(
            name='DroneRole',
        ),
    ]
