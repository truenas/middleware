from __future__ import unicode_literals


import json


from django.db import migrations
from freenasUI.freeadmin.models.fields import ListField


def ip_update(apps, schema_editor):

    settings_obj = apps.get_model('system', 'settings').objects.order_by('-id')[0]
    for key in ['stg_guiaddress', 'stg_guiv6address']:
        if getattr(settings_obj, key):
            setattr(settings_obj, key, json.dumps([getattr(settings_obj, key)]))
    settings_obj.save()


class Migration(migrations.Migration):

    dependencies = [
        ('system', '0029_add_organizational_unit'),
    ]

    operations = [
        migrations.RunPython(
            ip_update
        ),
        migrations.AlterField(
            model_name='settings',
            name='stg_guiaddress',
            field=ListField(default=['0.0.0.0'], verbose_name='WebGUI IPv4 Address', blank=True)
        ),
        migrations.AlterField(
            model_name='settings',
            name='stg_guiv6address',
            field=ListField(default=['::'], verbose_name='WebGUI IPv6 Address', blank=True)
        )
    ]
