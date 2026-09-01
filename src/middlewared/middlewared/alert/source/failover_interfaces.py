# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from middlewared.alert.applicability import APPLIANCE_OR_HA_LICENSED, HA_LICENSED
from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, AlertSource, Alert


class NoCriticalFailoverInterfaceFoundAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = 'At Least 1 Network Interface Is Required To Be Marked Critical For Failover'
    text = 'At least 1 network interface is required to be marked critical for failover.'
    applies_to = APPLIANCE_OR_HA_LICENSED
    listed_only_when = HA_LICENSED


class FailoverCriticalAlertSource(AlertSource):
    applies_to = HA_LICENSED
    post_failover_blackout = True
    run_on_backup_node = False

    async def check(self):
        if not await self.middleware.call('interface.query', [('failover_critical', '=', True)]):
            return [Alert(NoCriticalFailoverInterfaceFoundAlertClass)]
        else:
            return []
