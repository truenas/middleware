# Copyright (c) 2015 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

import os

from freenasUI.freeadmin.sqlite3_ha.base import Journal

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource

SYNC_FILE = '/var/tmp/sync_failed'


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

    def check_sync(self):
        if os.path.exists(SYNC_FILE) or not Journal.is_empty():
            return Alert(FailoverSyncFailedAlertClass)
