import django.core.validators
from django.db import migrations, models
import freenasUI.freeadmin.models.fields

def remove_sssd_aux_params(apps, schema_editor):
    LDAP = apps.get_model('directoryservice.LDAP')
    for o in LDAP.objects.all():
        if not o.ldap_anonbind:
            o.ldap_auxiliary_parameters = ""
            o.save()

class Migration(migrations.Migration):

    dependencies = [
        ('directoryservice', '0006_certificate_model'),
    ]

    operations = [
        migrations.RunPython(
            remove_sssd_aux_params 
        ),
    ]
