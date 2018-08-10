from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('system', '0027_add_organizational_unit'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='settings',
            name='stg_guiprotocol',
        )
    ]