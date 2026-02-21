from django.db import migrations, models
import django.db.models.deletion


def migrate_components(apps, schema_editor):
    Component = apps.get_model('equipment_accounting', 'Component')
    ContentType = apps.get_model('contenttypes', 'ContentType')

    # Battery components
    try:
        battery_ct = ContentType.objects.get(app_label='equipment_accounting', model='batterytype')
        BatteryType = apps.get_model('equipment_accounting', 'BatteryType')
        for comp in Component.objects.filter(content_type=battery_ct):
            comp.kind = 'battery'
            try:
                bt = BatteryType.objects.get(pk=comp.object_id)
                comp.power_template_id = bt.power_template_id
            except Exception:
                pass
            comp.save()
    except ContentType.DoesNotExist:
        pass

    # Spool components
    try:
        spool_ct = ContentType.objects.get(app_label='equipment_accounting', model='spooltype')
        SpoolType = apps.get_model('equipment_accounting', 'SpoolType')
        for comp in Component.objects.filter(content_type=spool_ct):
            comp.kind = 'spool'
            try:
                st = SpoolType.objects.get(pk=comp.object_id)
                comp.video_template_id = st.video_template_id
            except Exception:
                pass
            comp.save()
    except ContentType.DoesNotExist:
        pass

    # Other components
    try:
        other_ct = ContentType.objects.get(app_label='equipment_accounting', model='othercomponenttype')
        for comp in Component.objects.filter(content_type=other_ct):
            comp.kind = 'other'
            comp.other_type_id = comp.object_id
            comp.save()
    except ContentType.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('equipment_accounting', '0015_soft_delete_templates'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='component',
            name='kind',
            field=models.CharField(
                blank=True,
                choices=[('battery', 'Батарея'), ('spool', 'Котушка'), ('other', 'Інше')],
                max_length=10,
                verbose_name='Вид',
            ),
        ),
        migrations.AddField(
            model_name='component',
            name='power_template',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='battery_components',
                to='equipment_accounting.powertemplate',
                verbose_name='Шаблон живлення',
            ),
        ),
        migrations.AddField(
            model_name='component',
            name='video_template',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='spool_components',
                to='equipment_accounting.videotemplate',
                verbose_name='Шаблон відео',
            ),
        ),
        migrations.AddField(
            model_name='component',
            name='other_type',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='components',
                to='equipment_accounting.othercomponenttype',
                verbose_name='Тип',
            ),
        ),
        migrations.RunPython(migrate_components, migrations.RunPython.noop),
    ]
