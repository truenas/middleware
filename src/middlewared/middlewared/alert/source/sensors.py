# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

import time

from middlewared.alert.base import (
    AlertClass,
    AlertCategory,
    AlertLevel,
    AlertSource,
    Alert,
    UnavailableException,
)
from middlewared.utils import ProductType
from middlewared.utils.crypto import generate_token


class SensorAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = "Sensor Value Is Outside of Working Range"
    text = "Sensor %(name)s is %(relative)s %(level)s value: %(value)s %(event)s"
    products = (ProductType.ENTERPRISE,)


class PowerSupplyAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = "Power Supply Error"
    text = (
        "%(psu)s is %(state)s showing: %(errors)s. Contact support. Incident ID: %(id)s"
    )
    products = (ProductType.ENTERPRISE,)
    proactive_support = True
    proactive_support_notify_gone = True


class PsuAlertSource(AlertSource):
    def __init__(self, middleware):
        super().__init__(middleware)
        self.last_failure = time.monotonic()
        self.incident_id = None
        self._30mins = 30 * 60

    async def should_alert(self):
        if (await self.middleware.call("system.dmidecode_info"))[
            "system-product-name"
        ].startswith("TRUENAS-R"):
            # r-series
            return True
        elif await self.middleware.call("failover.hardware") == "ECHOWARP":
            # m-series
            return True

        return False

    async def check(self):
        alerts = []
        if not await self.should_alert():
            return alerts

        for i in await self.middleware.call("ipmi.sensors.query"):
            if (
                i["type"] == "Power Supply" and
                i["state"] != "Nominal" and
                i["reading"] != "N/A" and
                i["event"]
            ):
                if time.monotonic() - self.last_failure > self._30mins:
                    # we assume a PSU alert that has been around longer than
                    # 30mins is justification for opening up a proactive ticket
                    if self.incident_id is None:
                        self.incident_id = generate_token(16, url_safe=True)
                    alerts.append(
                        Alert(
                            PowerSupplyAlertClass,
                            {
                                "id": self.incident_id,
                                "psu": i["name"],
                                "state": i["state"],
                                "errors": ", ".join(i["event"]),
                            },
                        )
                    )
                else:
                    raise UnavailableException()
        return alerts


class SensorsAlertSource(AlertSource):
    async def should_alert(self):
        if (await self.middleware.call("system.dmidecode_info"))[
            "system-product-name"
        ].startswith("TRUENAS-R"):
            # r-series
            return True
        elif await self.middleware.call("failover.hardware") == "ECHOWARP":
            # m-series
            return True

        return False

    async def check(self):
        alerts = []
        if not await self.should_alert():
            return alerts

        for sensor in await self.middleware.call("ipmi.sensors.query"):
            if (
                sensor["type"] != "Power Supply" and
                sensor["state"] != "Nominal" and
                sensor["reading"] != "N/A" and
                sensor["event"]
            ):
                reading = sensor["reading"]
                for key in (
                    "lower-non-recoverable",
                    "lower-critical",
                    "lower-non-critical",
                ):
                    if sensor[key] != "N/A" and reading < sensor[key]:
                        relative = "below"
                        level = (
                            "recommended" if key == "lower-non-critical" else "critical"
                        )
                        return Alert(
                            SensorAlertClass,
                            {
                                "name": sensor["name"],
                                "relative": relative,
                                "level": level,
                                "value": reading,
                                "event": ", ".join(sensor["event"]),
                            },
                        )

                for key in (
                    "upper-non-recoverable",
                    "upper-critical",
                    "upper-non-critical",
                ):
                    if sensor[key] != "N/A" and reading > sensor[key]:
                        relative = "above"
                        level = (
                            "recommended" if key == "upper-non-critical" else "critical"
                        )
                        return Alert(
                            SensorAlertClass,
                            {
                                "name": sensor["name"],
                                "relative": relative,
                                "level": level,
                                "value": reading,
                                "event": ", ".join(sensor["event"]),
                            },
                        )
        return alerts
