# Copyright (c) - iXsystems Inc.
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource

TITLE = 'Missing Network Interface On '
TEXT = 'Network interfaces %(interfaces)s present on '


class NetworkCardsMismatchOnStandbyNodeAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = TITLE + 'Standby Storage Controller'
    text = TEXT + 'active storage controller but missing on standby storage controller.'
    products = ('SCALE_ENTERPRISE',)


class NetworkCardsMismatchOnActiveNodeAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = TITLE + 'Active Storage Controller'
    text = TEXT + 'standby storage controller but missing on active storage controller.'
    products = ('SCALE_ENTERPRISE',)


class FailoverNetworkCardsAlertSource(AlertSource):
    products = ('SCALE_ENTERPRISE',)
    failover_related = True
    run_on_backup_node = False

    async def check(self):
        if (interfaces := await self.middleware.call('failover.mismatch_nics')):
            if interfaces['missing_remote']:
                return [Alert(
                    NetworkCardsMismatchOnStandbyNodeAlertClass, {'interfaces': ', '.join(interfaces['missing_remote'])}
                )]
            if interfaces['missing_local']:
                return [Alert(
                    NetworkCardsMismatchOnActiveNodeAlertClass, {'interfaces': ', '.join(interfaces['missing_local'])}
                )]
        return []
