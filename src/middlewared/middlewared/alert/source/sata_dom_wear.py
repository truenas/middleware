# Copyright (c) 2019 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

from datetime import timedelta

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource, IntervalSchedule


class SATADOMWearWarningAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = "SATA DOM Lifetime: Less Than 20% Left"
    text = "%(lifetime)d%% of lifetime left on SATA DOM %(disk)s."

    products = ("ENTERPRISE",)


class SATADOMWearCriticalAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = "SATA DOM Lifetime: Less Than 10% Left"
    text = "%(lifetime)d%% of lifetime left on SATA DOM %(disk)s."

    products = ("ENTERPRISE",)


class SATADOMWearAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(hours=1))

    products = ("ENTERPRISE",)

    async def check(self):
        alerts = []
        for disk in await self.middleware.call("disk.query"):
            lifetime = await self.middleware.call("disk.sata_dom_lifetime_left", disk["devname"])
            if lifetime is not None:
                if lifetime <= 0.1:
                    alerts.append(Alert(SATADOMWearCriticalAlertClass, {
                        "disk": disk["name"],
                        "lifetime": int(lifetime * 100 + 0.5),
                    }))
                elif lifetime <= 0.2:
                    alerts.append(Alert(SATADOMWearWarningAlertClass, {
                        "disk": disk["name"],
                        "lifetime": int(lifetime * 100 + 0.5),
                    }))

        return alerts
