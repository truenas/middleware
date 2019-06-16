import django.core.validators
from django.db import migrations, models
import freenasUI.freeadmin.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('directoryservice', '0012_remove_unix_extensions'),
    ]

    operations = [
        migrations.AddField(
            model_name='LDAP',
            name='ldap_disable_freenas_cache',
            field=models.BooleanField(
                verbose_name='Disable LDAP user/group cache',
                default=False,
                help_text=(
                    "Set to disable caching LDAP users and groups in large LDAP environments. "
                    "When caching is disabled, LDAP users and groups do not appear in dropdown "
                    "menus, but are still accepted when manually entered."
                )
            )
        )
    ]
