from django.db import migrations, models


def set_default_for_ups_shutdowncmd(apps, schema_editor):
    ups = apps.get_model('services.UPS').objects.latest('id')
    if ups.ups_shutdowncmd == '/sbin/shutdown -p now':
        ups.ups_shutdowncmd = None
        ups.save()


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0032_enabled'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ups',
            name='ups_shutdowncmd',
            field=models.CharField(
                blank=True,
                help_text='The command used to shutdown the server. You can use a custom command here to perform '
                          'other tasks before shutdown.default: /sbin/shutdown -p now',
                max_length=255,
                null=True,
                verbose_name='Shutdown Command'
            ),
        ),
        migrations.RunPython(
            set_default_for_ups_shutdowncmd 
        ),
    ]
