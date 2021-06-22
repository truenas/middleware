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
    products = ("ENTERPRISE",)

    async def check(self):
        baseboard_manufacturer = (
            await self.middleware.call('system.dmidecode_info')
        )['baseboard-manufacturer']

        failover_hardware = await self.middleware.call("failover.hardware")

        is_gigabyte = baseboard_manufacturer == "GIGABYTE"
        is_m_series = baseboard_manufacturer == "Supermicro" and failover_hardware == "ECHOWARP"

        alerts = []
        for sensor in await self.middleware.call("sensor.query"):
            if is_gigabyte:
                if sensor["value"] is None:
                    continue

                if not (RE_CPUTEMP.match(sensor["name"]) or RE_SYSFAN.match(sensor["name"])):
                    continue

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
                    continue

                alerts.append(Alert(
                    SensorAlertClass,
                    {
                        "name": sensor["name"],
                        "relative": relative,
                        "level": level,
                        "value": sensor["value"],
                        "desc": sensor["desc"],
                    },
                    key=[sensor["name"], relative, level],
                ))

            if is_m_series:
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
