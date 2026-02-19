"""
The is_unusable field was declared in the initial migration but never actually
created in the database.  This migration adds the missing column to both
concrete drone-type tables.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('equipment_accounting', '0002_remove_uavinstance_serial_number'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE equipment_accounting_fpvdronetype ADD COLUMN is_unusable bool NOT NULL DEFAULT 0;",
            reverse_sql="ALTER TABLE equipment_accounting_fpvdronetype DROP COLUMN is_unusable;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE equipment_accounting_opticaldronetype ADD COLUMN is_unusable bool NOT NULL DEFAULT 0;",
            reverse_sql="ALTER TABLE equipment_accounting_opticaldronetype DROP COLUMN is_unusable;",
        ),
    ]
