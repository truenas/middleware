# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from typing import Any

from middlewared.alert.applicability import APPLIANCE_OR_HA_LICENSED, HA_LICENSED
from middlewared.alert.base import Alert, AlertCategory, AlertClass, AlertClassConfig, AlertLevel, AlertSource
from middlewared.utils import ProductType


class NoCriticalFailoverInterfaceFoundAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HA,
        level=AlertLevel.CRITICAL,
        title='At Least 1 Network Interface Is Required To Be Marked Critical For Failover',
        text='At least 1 network interface is required to be marked critical for failover.',
        products=(ProductType.ENTERPRISE,),
        applies_to=APPLIANCE_OR_HA_LICENSED,
        listed_only_when=HA_LICENSED,
    )


class FailoverCriticalAlertSource(AlertSource):
    products = (ProductType.ENTERPRISE,)
    applies_to = HA_LICENSED
    failover_related = True
    run_on_backup_node = False

    async def check(self) -> list[Alert[Any]]:
        if not await self.middleware.call('interface.query', [('failover_critical', '=', True)]):
            return [Alert(NoCriticalFailoverInterfaceFoundAlert())]
        else:
            return []
