from django.db import migrations


def resilver_value_update(apps, schema_editor):

    resilver_obj = apps.get_model('storage', 'resilver').objects.order_by('-id')[0]
    if not resilver_obj.weekday:
        resilver_obj.weekday = '1,2,3,4,5,6,7'
        resilver_obj.enabled = False
        resilver_obj.save()


def snapshot_value_update(apps, schema_editor):

    snapshot_model = apps.get_model('storage', 'task')
    for obj in snapshot_model.objects.all():
        if not obj.task_byweekday:
            obj.task_byweekday = '1,2,3,4,5,6,7'
            obj.task_enabled = False
            obj.save()


class Migration(migrations.Migration):

    dependencies = [
        ('storage', '0010_auto_20180618_0340'),
    ]

    operations = [
        migrations.RunPython(
            resilver_value_update
        ),
        migrations.RunPython(
            snapshot_value_update
        )
    ]
