from __future__ import unicode_literals

from django.db import migrations, models


def add_netdata_user(apps, schema_editor):
    try:
        group = apps.get_model("account", "bsdGroups").objects.create(
            bsdgrp_builtin=True,
            bsdgrp_gid="302",
            bsdgrp_group="netdata"
        )
        group.save()
        user = apps.get_model("account", "bsdUsers").objects.create(
            bsdusr_builtin=True,
            bsdusr_full_name="NetData Daemon",
            bsdusr_group=group,
            bsdusr_home="/var/cache/netdata",
            bsdusr_shell="/usr/sbin/nologin",
            bsdusr_smbhash="*",
            bsdusr_unixhash="*",
            bsdusr_uid="302",
            bsdusr_username="netdata"
        )
        user.save()

    except Exception as e:
        print("ERROR: unable to create netdata user/group: ", e)


def remove_netdata_user(apps, schema_editor):
    try:
        apps.get_model("account", "bsdUsers").objects.get(
            bsdusr_username="netdata"
        ).delete()
        apps.get_model("account", "bsdGroups").objects.get(
            bsdgrp_group="netdata"
        ).delete()

    except Exception as e:
        print("ERROR: unable to remove netdata user/group: ", e)


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0004_add_minio_user'),
    ]

    operations = [
        migrations.RunPython(
            add_netdata_user,
            reverse_code=remove_netdata_user
        )
    ]
