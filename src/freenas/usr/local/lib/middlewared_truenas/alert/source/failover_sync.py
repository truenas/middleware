# Copyright (c) 2015 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

import os

from freenasUI.freeadmin.sqlite3_ha.base import Journal

from middlewared.alert.base import Alert, AlertLevel, ThreadedAlertSource

SYNC_FILE = '/var/tmp/sync_failed'


class FailoverSyncAlert(ThreadedAlertSource):
    level = AlertLevel.CRITICAL
    title = 'Automatic sync to peer failed, please run it manually'

    def check_sync(self):
        if os.path.exists(SYNC_FILE) or not Journal.is_empty():
            return Alert()
