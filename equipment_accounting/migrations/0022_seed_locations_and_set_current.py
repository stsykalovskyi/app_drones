"""
Data migration:
1. Seed the five default Location records (workshop, manufacturer, brigade, dusha, position).
2. Set current_location = Майстерня for all existing UAVInstance records.
"""
from django.db import migrations

LOCATIONS = [
    ('Майстерня', 'workshop'),
    ('Виробник',  'manufacturer'),
    ('Бригада',   'brigade'),
    ('Дюша',      'dusha'),
    ('Позиція',   'position'),
]


def seed_locations(apps, schema_editor):
    Location = apps.get_model('equipment_accounting', 'Location')
    UAVInstance = apps.get_model('equipment_accounting', 'UAVInstance')

    # Create locations (idempotent — skip if already exists)
    for name, loc_type in LOCATIONS:
        Location.objects.get_or_create(name=name, defaults={'location_type': loc_type})

    # Assign Майстерня as the current location for all existing UAVs
    workshop = Location.objects.get(name='Майстерня')
    UAVInstance.objects.filter(current_location__isnull=True).update(current_location=workshop)


def reverse_seed(apps, schema_editor):
    # No-op: leaving locations in place on reverse is harmless
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('equipment_accounting', '0021_location_and_uavmovement'),
    ]

    operations = [
        migrations.RunPython(seed_locations, reverse_seed),
    ]
