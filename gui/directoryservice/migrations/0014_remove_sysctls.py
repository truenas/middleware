from django.db import migrations, models

def remove_sysctls(apps, schema_editor):
    fn_sysctl = [
        'freenas.services.domaincontroller.timeout.reload',
        'freenas.services.domaincontroller.timeout.restart',
        'freenas.services.domaincontroller.timeout.started',
        'freenas.services.domaincontroller.timeout.stop',
        'freenas.services.domaincontroller.timeout.start',
        'freenas.directoryservice.kerberos.error.last_error',
        'freenas.directoryservice.kerberos.timeout.reload',
        'freenas.directoryservice.kerberos.timeout.restart',
        'freenas.directoryservice.kerberos.timeout.started',
        'freenas.directoryservice.kerberos.timeout.stop',
        'freenas.directoryservice.kerberos.timeout.start',
        'freenas.directoryservice.nis.enumerate',
        'freenas.directoryservice.nis.cache',
        'freenas.directoryservice.nis.timeout.reload',
        'freenas.directoryservice.nis.timeout.restart',
        'freenas.directoryservice.nis.timeout.started',
        'freenas.directoryservice.nis.timeout.stop',
        'freenas.directoryservice.nis.timeout.start',
        'freenas.directoryservice.ldap.enumerate',
        'freenas.directoryservice.ldap.cache',
        'freenas.directoryservice.ldap.error.last_error',
        'freenas.directoryservice.ldap.timeout.reload',
        'freenas.directoryservice.ldap.timeout.restart',
        'freenas.directoryservice.ldap.timeout.started',
        'freenas.directoryservice.ldap.timeout.stop',
        'freenas.directoryservice.ldap.timeout.start',
        'freenas.directoryservice.activedirectory.enumerate',
        'freenas.directoryservice.activedirectory.cache',
        'freenas.directoryservice.activedirectory.dns.timeout',
        'freenas.directoryservice.activedirectory.dns.lifetime',
        'freenas.directoryservice.activedirectory.timeout.reload',
        'freenas.directoryservice.activedirectory.timeout.restart',
        'freenas.directoryservice.activedirectory.timeout.started',
        'freenas.directoryservice.activedirectory.timeout.stop',
        'freenas.directoryservice.activedirectory.timeout.start',
        'freenas.directoryservice.timeout.reload',
        'freenas.directoryservice.timeout.restart',
        'freenas.directoryservice.timeout.started',
        'freenas.directoryservice.timeout.stop',
        'freenas.directoryservice.timeout.start'
    ]
    sysctls = apps.get_model('system', 'tunable')
    for s in fn_sysctl:
        to_delete = sysctls.objects.filter(tun_type='sysctl',
                                           tun_var=s)
        if to_delete.exists():
            to_delete.delete()


class Migration(migrations.Migration):
    dependencies = [
        ('directoryservice', '0013_add_disable_freenas_cache_to_ldap'),
    ]

    operations = [
        migrations.RunPython(remove_sysctls, reverse_code=migrations.RunPython.noop),
    ]
