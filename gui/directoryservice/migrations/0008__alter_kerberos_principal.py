import django.core.validators
from django.db import migrations, models
import freenasUI.freeadmin.models.fields

def migrate_kerberos_principal(apps, schema_editor):
    LDAP = apps.get_model('directoryservice.LDAP')
    for o in LDAP.objects.all():
        if o.ldap_kerberos_principal:
            o.ldap_kerberos_principal_new = o.ldap_kerberos_principal.principal_name
            o.save()
    AD = apps.get_model('directoryservice.ActiveDirectory')
    for o in AD.objects.all():
        if o.ad_kerberos_principal:
            o.ad_kerberos_principal_new = o.ad_kerberos_principal.principal_name 
            o.save()


class Migration(migrations.Migration):

    dependencies = [
        ('directoryservice', '0007_migrate_to_nslcd'),
    ]

    operations = [
        migrations.AddField(
            model_name='ActiveDirectory',
            name='ad_kerberos_principal_new',
            field=models.CharField(blank=True, max_length=255, verbose_name='Kerberos Principal')
        ),
        migrations.AddField(
            model_name='LDAP',
            name='ldap_kerberos_principal_new',
            field=models.CharField(blank=True, max_length=255, verbose_name='Kerberos Principal')
        ),
        migrations.RunPython(
            migrate_kerberos_principal 
        ),
        migrations.RemoveField(
            model_name='ActiveDirectory',
            name='ad_kerberos_principal',
        ),
        migrations.RemoveField(
            model_name='LDAP',
            name='ldap_kerberos_principal',
        ),
        migrations.RenameField(
            model_name='ActiveDirectory',
            old_name='ad_kerberos_principal_new',
            new_name='ad_kerberos_principal',
        ),
        migrations.RenameField(
            model_name='LDAP',
            old_name='ldap_kerberos_principal_new',
            new_name='ldap_kerberos_principal',
        ),
        migrations.DeleteModel(
            name='KerberosPrincipal',
        )
    ]
