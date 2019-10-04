import contextlib

from django.db import migrations, models


def remove_netdata_user(apps, schema_editor):
    for model_name, field in (('bsdUsers', 'bsdusr_username'), ('bsdGroups', 'bsdgrp_group')):
        with contextlib.suppress(models.ObjectDoesNotExist):
            apps.get_model('account', model_name).objects.get(
                **{field: 'netdata'}
            ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0010_auto_20190221_0824'),
    ]

    operations = [
        migrations.RunPython(
            remove_netdata_user,
        )
    ]
