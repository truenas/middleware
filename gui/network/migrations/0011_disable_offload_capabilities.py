from django.db import migrations, models


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
        ('network', '0010_auto_20181114_1129'),
    ]

    operations = [
        migrations.AddField(
            model_name='interfaces',
            name='int_disable_offload_capabilities',
            field=models.BooleanField(default=False, verbose_name='Disable offload capabilities'),
        ),
        migrations.RunPython(
            disable_capabilities,
        )
    ]
