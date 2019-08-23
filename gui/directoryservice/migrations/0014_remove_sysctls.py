from django.db import migrations, models

def remove_sysctls(apps, schema_editor):
    sysctls = apps.get_model('system', 'tunable')
    sysctls.objects.filter(tun_type='sysctl', tun_var__startswith='freenas.').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('directoryservice', '0013_add_disable_freenas_cache_to_ldap'),
    ]

    operations = [
        migrations.RunPython(remove_sysctls, reverse_code=migrations.RunPython.noop),
    ]
