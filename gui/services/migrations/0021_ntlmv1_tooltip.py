# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import freenasUI.freeadmin.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0020_make_lunid_non_null'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cifs',
            name='cifs_srv_ntlmv1_auth',
            field=models.BooleanField(default=False,
                                      help_text=(
                                          'Off by default. When set, smbd(8) attempts '
                                          'to authenticate users with the insecure '
                                          'and vulnerable NTLMv1 encryption. This setting '
                                          'allows backward compatibility with older '
                                          'versions of Windows, but is not '
                                          'recommended and should not be used on untrusted '
                                          'networks.'
                                      ),
                                      verbose_name='NTLMv1 auth'),
        ),
    ]
