from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sharing', '0016_enabled'),
    ]

    operations = [
        migrations.AddField(
            model_name='cifs_share',
            name='cifs_share_acl',
            field=models.TextField(default='', verbose_name='SMB Share ACL'),
        ),
    ]
