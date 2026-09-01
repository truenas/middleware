# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from middlewared.alert.applicability import APPLIANCE_OR_HA_LICENSED, HA_LICENSED
from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource

TITLE = 'Missing Network Interface On '
TEXT = 'Network interfaces %(interfaces)s present on '


class NetworkCardsMismatchOnStandbyNodeAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = TITLE + 'Standby Storage Controller'
    text = TEXT + 'active storage controller but missing on standby storage controller.'
    applies_to = APPLIANCE_OR_HA_LICENSED
    listed_only_when = HA_LICENSED


class NetworkCardsMismatchOnActiveNodeAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = TITLE + 'Active Storage Controller'
    text = TEXT + 'standby storage controller but missing on active storage controller.'
    applies_to = APPLIANCE_OR_HA_LICENSED
    listed_only_when = HA_LICENSED


class FailoverNetworkCardsAlertSource(AlertSource):
    applies_to = HA_LICENSED
    post_failover_blackout = True
    require_stable_peer = True
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
