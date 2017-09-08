# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-08-14 01:39
from __future__ import unicode_literals

import django.core.validators
from django.db import migrations, models
import freenasUI.freeadmin.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('directoryservice', '0003_kill_nt4'),
    ]

    operations = [
        migrations.CreateModel(
            name='idmap_none',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('idmap_ds_type', models.IntegerField(null=True)),
                ('idmap_ds_id', models.PositiveIntegerField(null=True)),
            ],
            options={
                'verbose_name': 'NONE Idmap',
                'verbose_name_plural': 'NONE Idmap',
            },
        ),
        migrations.CreateModel(
            name='idmap_script',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('idmap_ds_type', models.IntegerField(null=True)),
                ('idmap_ds_id', models.PositiveIntegerField(null=True)),
                ('idmap_script_range_low', models.IntegerField(default=90000001, verbose_name='Range Low')),
                ('idmap_script_range_high', models.IntegerField(default=100000000, verbose_name='Range High')),
                ('idmap_script_script', freenasUI.freeadmin.models.fields.PathField(help_text='This option is used to configure an external program for performing id mappings. This is read-only backend and relies on winbind_cache tdb to store obtained values', max_length=255, verbose_name='Script')),
            ],
            options={
                'verbose_name': 'Script Idmap',
                'verbose_name_plural': 'Script Idmap',
            },
        ),
    ]
