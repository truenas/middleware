from __future__ import unicode_literals

from django.db import migrations


def correct_default_value_for_https_redirect(apps, schema_editor):
    settings_model = apps.get_model('system', 'settings')
    settings = settings_model.objects.order_by('-id')[0]
    if settings.stg_guiprotocol != 'HTTPS':
        settings.stg_guihttpsredirect = False
        settings.save()


class Migration(migrations.Migration):

    dependencies = [
        ('system', '0031_adv_boot_scrub'),
    ]

    operations = [
        migrations.RunPython(
            correct_default_value_for_https_redirect
        ),
        migrations.RemoveField(
            model_name='settings',
            name='stg_guiprotocol',
        )
    ]
