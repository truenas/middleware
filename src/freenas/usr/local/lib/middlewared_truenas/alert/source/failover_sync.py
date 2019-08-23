# Copyright (c) 2015 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource


class FailoverSyncFailedAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = "Automatic Sync to Peer Failed"
    text = (
        "Failed to sync configuration information to passive storage "
        "controller. Use Sync to Peer on the System/Failover page to "
        "perform a manual sync."
    )


class FailoverSyncAlert(ThreadedAlertSource):
    failover_related = True
    run_on_backup_node = False

    async def check(self):
        if await self.middleware.call('failover.database_sync_failed'):
            return Alert(FailoverSyncFailedAlertClass)
