# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from dataclasses import dataclass
from typing import Any

from middlewared.alert.base import Alert, AlertCategory, AlertClass, AlertClassConfig, AlertLevel, AlertSource
from middlewared.utils import ProductType

TITLE = "Missing Network Interface On "
TEXT = "Network interfaces %(interfaces)s present on "


@dataclass(kw_only=True)
class NetworkCardsMismatchOnStandbyNodeAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HA,
        level=AlertLevel.CRITICAL,
        title=TITLE + "Standby Storage Controller",
        text=TEXT + "active storage controller but missing on standby storage controller.",
        products=(ProductType.ENTERPRISE,),
    )

    interfaces: str


@dataclass(kw_only=True)
class NetworkCardsMismatchOnActiveNodeAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HA,
        level=AlertLevel.CRITICAL,
        title=TITLE + "Active Storage Controller",
        text=TEXT + "standby storage controller but missing on active storage controller.",
        products=(ProductType.ENTERPRISE,),
    )

    interfaces: str


class FailoverNetworkCardsAlertSource(AlertSource):
    products = (ProductType.ENTERPRISE,)
    failover_related = True
    require_stable_peer = True
    run_on_backup_node = False

    async def check(self) -> list[Alert[Any]]:
        if (interfaces := await self.middleware.call("failover.mismatch_nics")):
            if interfaces["missing_remote"]:
                return [Alert(
                    NetworkCardsMismatchOnStandbyNodeAlert(interfaces=", ".join(interfaces["missing_remote"]))
                )]
            if interfaces["missing_local"]:
                return [Alert(
                    NetworkCardsMismatchOnActiveNodeAlert(interfaces=", ".join(interfaces["missing_local"]))
                )]
        return []
