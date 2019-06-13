import django.core.validators
from django.db import migrations, models
import freenasUI.freeadmin.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('directoryservice', '0011_add_new_idmap_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='LDAP',
            name='ldap_disable_freenas_cache',
            field=models.BooleanField(
                verbose_name='Disable LDAP user/group cache',
                default=False,
                help_text=(
                    "Set this if you want to disable caching LDAP users "
                    "and groups. This is an optimization for large LDAP  "
                    "Environments. If caching is disabled, then LDAP users "
                    "and groups will not appear in dropdown menus, but will "
                    "still be accepted if manually entered.",
                )
            )
        )
    ]
