from django.db import migrations, models


def migrate_to_ldaps_ad(apps, schema_editor):
    AD = apps.get_model(f'directoryservice.activedirectory')
    for o in AD.objects.all():
        if o.ad_dns_timeout == 60:
            o.ad_dns_timeout = 10

        if not o.ad_enable:
            o.ad_ldap_sasl_wrapping = 'sign'

        o.save()


class Migration(migrations.Migration):

    dependencies = [
        ('directoryservice', '0014_remove_sysctls'),
    ]

    operations = [
        migrations.AddField(
            model_name='ActiveDirectory',
            name='ad_validate_certificates',
            field=models.BooleanField(
                verbose_name='Perform strict certificate validation',
                default=True,
                help_text=(
                    "Request certificate from remote LDAP server. If no certificate is provided "
                    "or a bad certificate is provided, immediately terminate LDAP session. "
                    "This parameter corresponds with the ldap.conf parameter TLS_REQCERT demand. "
                    "TLS_REQCERT allow is set if unchecked. "
                )
            )
        ),
        migrations.AddField(
            model_name='LDAP',
            name='ldap_validate_certificates',
            field=models.BooleanField(
                verbose_name='Perform strict certificate validation',
                default=True,
                help_text=(
                    "Request certificate from remote LDAP server. If no certificate is provided "
                    "or a bad certificate is provided, immediately terminate LDAP session. "
                    "This parameter corresponds with the ldap.conf parameter TLS_REQCERT demand. "
                    "TLS_REQCERT allow is set if unchecked. "
                )
            )
        ),
        migrations.RemoveField(model_name='LDAP', name='ldap_usersuffix'),
        migrations.RemoveField(model_name='LDAP', name='ldap_groupsuffix'),
        migrations.RemoveField(model_name='LDAP', name='ldap_passwordsuffix'),
        migrations.RemoveField(model_name='LDAP', name='ldap_machinesuffix'),
        migrations.RemoveField(model_name='LDAP', name='ldap_sudosuffix'),
        migrations.RunPython(migrate_to_ldaps_ad, reverse_code=migrations.RunPython.noop),
    ]
