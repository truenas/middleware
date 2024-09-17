# Copyright (c) - iXsystems Inc.
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, AlertSource, Alert


class NoCriticalFailoverInterfaceFoundAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = 'At Least 1 Network Interface Is Required To Be Marked Critical For Failover'
    text = 'At least 1 network interface is required to be marked critical for failover.'
    products = ('SCALE_ENTERPRISE',)


class FailoverCriticalAlertSource(AlertSource):
    products = ('SCALE_ENTERPRISE',)
    failover_related = True
    run_on_backup_node = False

    async def check(self):
        if not await self.middleware.call('interface.query', [('failover_critical', '=', True)]):
            return [Alert(NoCriticalFailoverInterfaceFoundAlertClass)]
        else:
            return []
