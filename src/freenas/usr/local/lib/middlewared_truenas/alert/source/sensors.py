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

PS_FAILURES = [
    (0x2, "Failure detected"),
    (0x4, "Predictive failure"),
    (0x8, "Power Supply AC lost"),
    (0x10, "AC lost or out-of-range"),
    (0x20, "AC out-of-range, but present"),
]


class SensorsAlertSource(ThreadedAlertSource):
    level = AlertLevel.CRITICAL
    title = "Sensors has bad value"

    def check_sync(self):
        proc = subprocess.Popen([
            "/usr/local/sbin/dmidecode",
            "-s",
            "baseboard-manufacturer",
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf8')
        baseboard_manufacturer = proc.communicate()[0].split("\n", 1)[0].strip()

        failover_hardware = self.middleware.call_sync("notifier.failover_hardware")

        is_gigabyte = baseboard_manufacturer == "GIGABYTE"
        is_m_series = baseboard_manufacturer == "Supermicro" and failover_hardware == "ECHOWARP"

        if not (is_gigabyte or is_m_series):
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

            for index in [1, 5, 6, 7, 8]:
                if fields[index] is None:
                    continue

                if fields[index].startswith("0x"):
                    try:
                        fields[index] = int(fields[index], 16)
                    except Exception:
                        fields[index] = None
                else:
                    try:
                        fields[index] = Decimal(fields[index])
                    except:
                        fields[index] = None

            name, value, desc, locrit, lowarn, hiwarn, hicrit = (
                fields[0],
                fields[1],
                fields[2],
                fields[5],
                fields[6],
                fields[7],
                fields[8],
            )

            if is_gigabyte:
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

            if is_m_series:
                ps_match = re.match("(PS[0-9]+) Status", name)
                if ps_match:
                    errors = []
                    if not (value & 0x1):
                        errors.append("No presence detected")
                    for b, title in PS_FAILURES:
                        if value & b:
                            errors.append(title)
                    if errors:
                        alerts.append(Alert(
                            Alert.CRIT,
                            "Power supply %s failed: %s",
                            args=[
                                ps_match.group(1),
                                ", ".join(errors),
                            ]
                        ))

        return alerts
