# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from middlewared.alert.applicability import HardwareClass, HardwareRule, LicenseRequirement, LicenseRule
from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource
from middlewared.utils import ProductType

TITLE = 'Missing Network Interface On '
TEXT = 'Network interfaces %(interfaces)s present on '


HA_LICENSED = LicenseRule(requirement=LicenseRequirement.HA)
TRUENAS_HARDWARE = HardwareRule(classes=frozenset({HardwareClass.TRUENAS_HW}))


class NetworkCardsMismatchOnStandbyNodeAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = TITLE + 'Standby Storage Controller'
    text = TEXT + 'active storage controller but missing on standby storage controller.'
    products = (ProductType.ENTERPRISE,)
    applies_to = TRUENAS_HARDWARE
    listed_when = HA_LICENSED


class NetworkCardsMismatchOnActiveNodeAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = TITLE + 'Active Storage Controller'
    text = TEXT + 'standby storage controller but missing on active storage controller.'
    products = (ProductType.ENTERPRISE,)
    applies_to = TRUENAS_HARDWARE
    listed_when = HA_LICENSED


class FailoverNetworkCardsAlertSource(AlertSource):
    products = (ProductType.ENTERPRISE,)
    applies_to = HA_LICENSED
    failover_related = True
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
