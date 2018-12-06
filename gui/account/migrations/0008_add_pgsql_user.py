# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from freenasUI.middleware.notifier import notifier

def add_pgsql_user(apps, schema_editor):
    if notifier().is_freenas():
        return

    try:
        group = apps.get_model("account", "bsdGroups").objects.create(
            bsdgrp_builtin=True,
            bsdgrp_gid="5432",
            bsdgrp_group="pgsql"
        )
        group.save()
        user = apps.get_model("account", "bsdUsers").objects.create(
            bsdusr_builtin=True,
            bsdusr_full_name="PostgreSQL Database User",
            bsdusr_group=group,
            bsdusr_home="/usr/local/pgsql",
            bsdusr_shell="/bin/sh",
            bsdusr_smbhash="*",
            bsdusr_unixhash="*",
            bsdusr_uid="5432",
            bsdusr_username="pgsql"
        )
        user.save()

    except Exception as e:
        print("ERROR: unable to create pgsql user/group: ", e)

def remove_pgsql_user(apps, schema_editor):
    if notifier().is_freenas():
        return

    try:
        apps.get_model("account", "bsdUsers").objects.get(
            bsdusr_username="pgsql"
        ).delete()
        apps.get_model("account", "bsdGroups").objects.get(
            bsdgrp_group="pgsql"
        ).delete()

    except Exception as e:
        print("ERROR: unable to remove pgsql user/group: ", e)

class Migration(migrations.Migration):
    dependencies = [
        ('account', '0007_add_nslcd_user'),
    ]

    operations = [
        migrations.RunPython(
            add_pgsql_user,
            reverse_code=remove_pgsql_user
        )
    ]
