# Copyright (c) - iXsystems Inc.
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource
from middlewared.utils import ProductType

TITLE = 'Disks Missing On '
TEXT = 'Disks with serial %(serials)s present on '


class DisksAreNotPresentOnStandbyNodeAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = TITLE + 'Standby Storage Controller'
    text = TEXT + 'active storage controller but missing on standby storage controller.'
    products = (ProductType.SCALE_ENTERPRISE,)


class DisksAreNotPresentOnActiveNodeAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = TITLE + 'Active Storage Controller'
    text = TEXT + 'standby storage controller but missing on active storage controller.'
    products = (ProductType.SCALE_ENTERPRISE,)


class FailoverDisksAlertSource(AlertSource):
    products = (ProductType.SCALE_ENTERPRISE,)
    failover_related = True
    run_on_backup_node = False

    async def check(self):
        if (md := await self.middleware.call('failover.mismatch_disks')):
            if md['missing_remote']:
                return [Alert(
                    DisksAreNotPresentOnStandbyNodeAlertClass, {'serials': ', '.join(md['missing_remote'])}
                )]
            if md['missing_local']:
                return [Alert(
                    DisksAreNotPresentOnActiveNodeAlertClass, {'serials': ', '.join(md['missing_local'])}
                )]
        return []
