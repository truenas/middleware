from __future__ import unicode_literals

from django.db import migrations


def correct_legacy_shell_value(apps, schema_editor):
    user_model = apps.get_model('account', 'bsdusers')
    for user in user_model.objects.all():
        if user.bsdusr_shell == '/sbin/nologin':
            user.bsdusr_shell = '/usr/sbin/nologin'
            user.save()


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0007_add_nslcd_user'),
    ]

    operations = [
        migrations.RunPython(
            correct_legacy_shell_value
        )
    ]
