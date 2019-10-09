from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sharing', '0013_remove_cifs_default_permissions'),
    ]

    operations = [
        migrations.AddField(
            model_name='cifs_share',
            name='cifs_timemachine',
            field=models.BooleanField(default=False, verbose_name='Time Machine over SMB'),
        ),
        migrations.AddField(
            model_name='cifs_share',
            name='cifs_vuid',
            field=models.CharField(blank=True, help_text='Volume UUID for _adisk._tcp. mDNS advertisment', max_length=36, verbose_name='Volume UUID')
        ),
    ]
