# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from dataclasses import dataclass
from typing import Any

from middlewared.alert.base import Alert, AlertCategory, AlertClass, AlertClassConfig, AlertLevel, AlertSource
from middlewared.utils import ProductType

TITLE = 'Disks Missing On '
TEXT = 'Disks with serial %(serials)s present on '


@dataclass(kw_only=True)
class DisksAreNotPresentOnStandbyNodeAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HA,
        level=AlertLevel.CRITICAL,
        title=TITLE + 'Standby Storage Controller',
        text=TEXT + 'active storage controller but missing on standby storage controller.',
        products=(ProductType.ENTERPRISE,),
    )

    serials: str


@dataclass(kw_only=True)
class DisksAreNotPresentOnActiveNodeAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HA,
        level=AlertLevel.CRITICAL,
        title=TITLE + 'Active Storage Controller',
        text=TEXT + 'standby storage controller but missing on active storage controller.',
        products=(ProductType.ENTERPRISE,),
    )

    serials: str


class FailoverDisksAlertSource(AlertSource):
    products = (ProductType.ENTERPRISE,)
    failover_related = True
    require_stable_peer = True
    run_on_backup_node = False

    async def check(self) -> list[Alert[Any]]:
        if (md := await self.middleware.call('failover.mismatch_disks')):
            if md['missing_remote']:
                return [Alert(
                    DisksAreNotPresentOnStandbyNodeAlert(serials=', '.join(md['missing_remote']))
                )]
            if md['missing_local']:
                return [Alert(
                    DisksAreNotPresentOnActiveNodeAlert(serials=', '.join(md['missing_local']))
                )]
        return []
