from __future__ import unicode_literals
from django.db import migrations

import sys


def add_netdata_to_services(apps, schema_editor):
    services = apps.get_model("services", "services")
    netdata = services.objects.create()
    netdata.srv_service = "netdata"
    netdata.srv_enable = False
    try:
        netdata.save()
    except Exception as error:
        print(f"ERROR: unable to add Netdata service: {error}", file=sys.stderr)


def remove_netdata_from_services(apps, schema_editor):
    services = apps.get_model("services", "services")
    netdata = services.objects.get(srv_service="netdata")
    try:
        netdata.delete()
    except Exception as error:
        print(f"ERROR: unable to remove Netdata service: {error}", file=sys.stderr)


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0006_servicemonitor'),
    ]

    operations = [
        migrations.RunPython(
            add_netdata_to_services,
            reverse_code=remove_netdata_from_services
        )
    ]
