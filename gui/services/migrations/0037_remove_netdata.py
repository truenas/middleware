from django.db import migrations


def remove_netdata(apps, schema_editor):
    services = apps.get_model('services', 'services')
    try:
        netdata = services.objects.get(srv_service='netdata')
    except services.DoesNotExist:
        pass
    else:
        netdata.delete()


class Migration(migrations.Migration):
    dependencies = [
        ('services', '0036_remove_smart_email'),
    ]

    operations = [
        migrations.RunPython(
            remove_netdata,
        ),
        migrations.DeleteModel(
            name='NetDataGlobalSettings',
        ),
    ]
