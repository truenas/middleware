# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from middlewared.alert.base import (
    AlertClass, AlertClassConfig, AlertCategory, AlertLevel, Alert, AlertSource, IntervalSchedule,
)
from middlewared.utils import ProductType


@dataclass(kw_only=True)
class SATADOMWearWarningAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HARDWARE,
        level=AlertLevel.WARNING,
        title="SATA DOM Lifetime: Less Than 20% Left",
        text="%(lifetime)d%% of lifetime left on SATA DOM %(disk)s.",
        products=(ProductType.ENTERPRISE,),
    )

    disk: str
    lifetime: int


@dataclass(kw_only=True)
class SATADOMWearCriticalAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HARDWARE,
        level=AlertLevel.CRITICAL,
        title="SATA DOM Lifetime: Less Than 10% Left",
        text="%(lifetime)d%% of lifetime left on SATA DOM %(disk)s.",
        products=(ProductType.ENTERPRISE,),
    )

    disk: str
    lifetime: int


class SATADOMWearAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(hours=1))
    products = (ProductType.ENTERPRISE,)

    async def check(self) -> list[Alert[Any]]:
        dmi = await self.middleware.call("system.dmidecode_info")
        if not dmi["system-product-name"].startswith(("TRUENAS-M", "TRUENAS-Z")):
            return []

        alerts: list[Alert[Any]] = []
        for disk in await self.middleware.call("boot.get_disks"):
            if not disk.startswith("sda"):
                continue

            lifetime = await self.middleware.call("disk.sata_dom_lifetime_left", disk)
            if lifetime is not None:
                if lifetime <= 0.1:
                    alerts.append(Alert(SATADOMWearCriticalAlert(
                        disk=disk,
                        lifetime=int(lifetime * 100 + 0.5),
                    )))
                elif lifetime <= 0.2:
                    alerts.append(Alert(SATADOMWearWarningAlert(
                        disk=disk,
                        lifetime=int(lifetime * 100 + 0.5),
                    )))

        return alerts
