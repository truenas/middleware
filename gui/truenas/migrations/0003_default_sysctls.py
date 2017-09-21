from django.db import migrations, models

def set_default_sysctls(apps, schema_editor):
    sysctl = apps.get_model('system', 'Tunable').objects.create()
    sysctl.tun_var = "freenas.directoryservice.activedirectory.timeout.start"
    sysctl.tun_value = "220"
    sysctl.tun_type = "sysctl"
    sysctl.tun_comment = "AD start timeout"
    sysctl.tun_enabled = True
    sysctl.save()

    sysctl = apps.get_model('system', 'Tunable').objects.create()
    sysctl.tun_var = "freenas.directoryservice.activedirectory.timeout.restart"
    sysctl.tun_value = "400"
    sysctl.tun_type = "sysctl"
    sysctl.tun_comment = "AD restart timeout"
    sysctl.tun_enabled = True
    sysctl.save()

class Migration(migrations.Migration):
    dependencies = [
        ('truenas', '0002_zseries_serial_port'),
    ]

    operations = [
        migrations.RunPython(set_default_sysctls),
    ]
