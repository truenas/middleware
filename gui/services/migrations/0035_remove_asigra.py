from django.db import migrations


def remove_asigra(apps, schema_editor):
    services = apps.get_model("services", "services")
    try:
        asigra = services.objects.get(srv_service="asigra")
    except services.DoesNotExist:
        pass
    else:
        asigra.delete()


class Migration(migrations.Migration):
    dependencies = [
        ('services', '0034_remove_extra_fields_smbconf'),
    ]

    operations = [
        migrations.RunPython(
            remove_asigra,
        )
    ]
