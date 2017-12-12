# -*- coding: utf-8 -*-

import os
import re
import subprocess
from django.db import migrations, models


def ha_hardware():
    hardware = ''
    enclosures = ["/dev/" + enc for enc in os.listdir("/dev") if enc.startswith("ses")]
    for enclosure in enclosures:
        proc = subprocess.Popen([
            '/usr/sbin/getencstat',
            '-V', enclosure,
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        encstat = proc.communicate()[0].decode('utf8', 'ignore').strip()
        # The echostream E16 JBOD and the echostream Z-series chassis are the same piece of hardware
        # One of the only ways to differentiate them is to look at the enclosure elements in detail
        # The Z-series chassis identifies element 0x26 as SD_9GV12P1J_12R6K4.  The E16 does not.
        # The E16 identifies element 0x25 as NM_3115RL4WB66_8R5K5
        # We use this fact to ensure we are looking at the internal enclosure, not a shelf.
        # If we used a shelf to determine which node was A or B you could cause the nodes to switch
        # identities by switching the cables for the shelf.
        if re.search("SD_9GV12P1J_12R6K4", encstat, re.M):
            hardware = 'ECHOSTREAM'
            break
    return hardware


def zseries_serial_port(apps, schema_editor):
    Advanced = apps.get_model('system', 'Advanced')
    for obj in Advanced.objects.all():
        if obj.adv_serialport == '0x2f8' and ha_hardware() == 'ECHOSTREAM':
            obj.adv_sertialport = '0x3f8'
            obj.save()


class Migration(migrations.Migration):

    dependencies = [
        ('truenas', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(zseries_serial_port),
    ]
