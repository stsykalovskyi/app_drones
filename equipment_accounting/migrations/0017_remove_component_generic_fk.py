from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('equipment_accounting', '0016_component_direct_templates'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.RemoveField(model_name='component', name='content_type'),
        migrations.RemoveField(model_name='component', name='object_id'),
        migrations.AlterField(
            model_name='component',
            name='kind',
            field=models.CharField(
                choices=[('battery', 'Батарея'), ('spool', 'Котушка'), ('other', 'Інше')],
                max_length=10,
                verbose_name='Вид',
            ),
        ),
        migrations.DeleteModel(name='BatteryType'),
        migrations.DeleteModel(name='SpoolType'),
    ]
