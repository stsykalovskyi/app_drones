from django.db import migrations


INITIAL_LOCATIONS = [
    ('Майстерня', 'workshop'),
    ('Виробник', 'manufacturer'),
    ('Дюша',     'dusha'),
    ('Позиція',  'position'),
]


def seed_locations(apps, schema_editor):
    """Ensure default locations exist; safe to run on a DB that already has them."""
    Location = apps.get_model('equipment_accounting', 'Location')
    for name, loc_type in INITIAL_LOCATIONS:
        Location.objects.get_or_create(name=name, defaults={'location_type': loc_type})


class Migration(migrations.Migration):

    dependencies = [
        ('equipment_accounting', '0030_replace_position_name_with_fk'),
    ]

    operations = [
        migrations.RunPython(seed_locations, migrations.RunPython.noop),
    ]
