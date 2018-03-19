# Copyright (c) 2015 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

from decimal import Decimal
import re
import subprocess

from middlewared.alert.base import Alert, AlertLevel, ThreadedAlertSource

RE_CPUTEMP = re.compile(r'^cpu.*temp$', re.I)
RE_SYSFAN = re.compile(r'^sys_fan\d+$', re.I)


class SensorsAlertSource(ThreadedAlertSource):
    level = AlertLevel.CRITICAL
    title = "Sensors has bad value"

    def check_sync(self):
        proc = subprocess.Popen([
            "/usr/local/sbin/dmidecode",
            "-s",
            "baseboard-manufacturer",
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf8')
        if proc.communicate()[0].split('\n', 1)[0].strip() != "GIGABYTE":
            return

        proc = subprocess.Popen([
            "/usr/local/bin/ipmitool",
            "sensor",
            "list",
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf8')

        data = proc.communicate()[0].strip('\n')
        alerts = []

        for line in data.split('\n'):
            fields = [field.strip(' ') for field in line.split('|')]
            fields = [None if field == 'na' else field for field in fields]

            if fields[1] is not None:
                try:
                    fields[1] = Decimal(fields[1])
                except:
                    fields[1] = None

            for i, val in enumerate(fields[5:9]):
                if val is None:
                    continue
                try:
                    fields[5 + i] = Decimal(val)
                except:
                    fields[5 + i] = None

            name, value, desc, locrit, lowarn, hiwarn, hicrit = (
                fields[0],
                fields[1],
                fields[2],
                fields[5],
                fields[6],
                fields[7],
                fields[8],
            )

            if value is None:
                continue

            if not(RE_CPUTEMP.match(name) or RE_SYSFAN.match(name)):
                continue

            if lowarn and value < lowarn:
                relative = 'below'
                if value < locrit:
                    level = 'critical'
                else:
                    level = 'recommended'

            elif hiwarn and value > hiwarn:
                relative = 'above'
                if value > hicrit:
                    level = 'critical'
                else:
                    level = 'recommended'
            else:
                continue

            alerts.append(Alert(
                Alert.CRIT,
                'Sensor %s is %s %s value: %d %s',
                args=[
                    name,
                    relative,
                    level,
                    value,
                    desc,
                ]
            ))

        return alerts
