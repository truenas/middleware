from __future__ import unicode_literals
from django.db import migrations

import sys

from freenasUI.middleware.notifier import notifier

def add_asigra(apps, schema_editor):
    if notifier().is_freenas():
        return 

    services = apps.get_model("services", "services")
    asigra = services.objects.create()
    asigra.srv_service = "asigra"
    asigra.srv_enable = False
    try:
        asigra.save()
    except Exception as error:
        print(f"ERROR: unable to add Asigra service: {error}", file=sys.stderr)


def remove_asigra(apps, schema_editor):
    if notifier().is_freenas():
        return 

    services = apps.get_model("services", "services")
    asigra = services.objects.get(srv_service="asigra")
    try:
        asigra.delete()
    except Exception as error:
        print(f"ERROR: unable to remove Asigra service: {error}", file=sys.stderr)


class Migration(migrations.Migration):
    dependencies = [
        ('services', '0017_ftp_set_unlimited_length_for_ftp_options'),
    ]

    operations = [
        migrations.RunPython(
            add_asigra,
            reverse_code=remove_asigra
        )
    ]
