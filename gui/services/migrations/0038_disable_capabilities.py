from django.db import migrations


def disable_capabilities(apps, schema_editor):
    asigra = apps.get_model('services', 'asigra').objects.all()
    if asigra:
        asigra = asigra[0]
        if asigra.filesystem:
            # Disable capabilities for all interfaces
            for nic in apps.get_model('network', 'interfaces').objects.all():
                nic.int_disable_offload_capabilities = True
                nic.save()


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0037_remove_netdata'),
        ('network', '0011_disable_offload_capabilities'),
    ]

    operations = [
        migrations.RunPython(
            disable_capabilities,
        )
    ]
