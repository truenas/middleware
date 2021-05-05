# Copyright (c) 2020 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

import logging
import re

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, AlertSource, Alert

logger = logging.getLogger(__name__)

RE_CPUTEMP = re.compile(r'^cpu.*temp$', re.I)
RE_SYSFAN = re.compile(r'^sys_fan\d+$', re.I)

PS_FAILURES = [
    (0x2, "Failure detected"),
    (0x4, "Predictive failure"),
    (0x8, "Power Supply AC lost"),
    (0x10, "AC lost or out-of-range"),
    (0x20, "AC out-of-range, but present"),
]


class SensorAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = "Sensor Value Is Outside of Working Range"
    text = "Sensor %(name)s is %(relative)s %(level)s value: %(value)d %(description)s"

    products = ("ENTERPRISE",)


class PowerSupplyAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = "Power Supply Failed"
    text = "Power supply %(number)s failed: %(errors)s."

    products = ("ENTERPRISE",)


class SensorsAlertSource(AlertSource):
    async def check(self):
        dmidecode_info = await self.middleware.call('system.dmidecode_info')
        baseboard_manufacturer = dmidecode_info['baseboard-manufacturer']
        system_product_name = dmidecode_info['system-product-name']

        failover_hardware = await self.middleware.call("failover.hardware")

        is_ix_hardware = await self.middleware.call("system.is_ix_hardware")
        is_gigabyte = baseboard_manufacturer == "GIGABYTE"
        is_m_series = baseboard_manufacturer == "Supermicro" and failover_hardware == "ECHOWARP"
        is_r_series = system_product_name.startswith("TRUENAS-R")
        is_freenas_certified = (
            baseboard_manufacturer == "Supermicro" and system_product_name.startswith("FREENAS-CERTIFIED")
        )

        alerts = []
        for sensor in await self.middleware.call("sensor.query"):
            if is_ix_hardware:
                if sensor["name"] == "BAT":
                    if alert := self._produce_sensor_alert(sensor):
                        alerts.append(alert)

            if is_gigabyte:
                if sensor["value"] is None:
                    continue

                if not (RE_CPUTEMP.match(sensor["name"]) or RE_SYSFAN.match(sensor["name"])):
                    continue

                if alert := self._produce_sensor_alert(sensor):
                    alerts.append(alert)

            if is_m_series or is_r_series or is_freenas_certified:
                ps_match = re.match("(PS[0-9]+) Status", sensor["name"])
                if ps_match:
                    ps = ps_match.group(1)

                    if sensor["notes"]:
                        alerts.append(Alert(
                            PowerSupplyAlertClass,
                            {
                                "number": ps,
                                "errors": ", ".join(sensor["notes"]),
                            }
                        ))

        return alerts

    def _produce_sensor_alert(self, sensor):
        if sensor["lowarn"] and sensor["value"] < sensor["lowarn"]:
            relative = "below"
            if sensor["value"] < sensor["locrit"]:
                level = "critical"
            else:
                level = "recommended"
        elif sensor["hiwarn"] and sensor["value"] > sensor["hiwarn"]:
            relative = "above"
            if sensor["value"] > sensor["hicrit"]:
                level = "critical"
            else:
                level = "recommended"
        else:
            return

        return Alert(
            SensorAlertClass,
            {
                "name": sensor["name"],
                "relative": relative,
                "level": level,
                "value": sensor["value"],
                "desc": sensor["desc"],
            },
            key=[sensor["name"], relative, level],
        )
