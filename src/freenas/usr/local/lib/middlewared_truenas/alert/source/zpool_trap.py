# Copyright (c) 2015 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

import os

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource


class ZpoolTrapAlertClass(AlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.CRITICAL
    title = "ZFS Pool Device Removal Detected"
    text = "%s"


class ZpoolTrapAlertSource(AlertSource):
    async def check(self):
        ZPOOL_TRAP_FILE = "/var/tmp/zpool_trap"
        if os.path.exists(ZPOOL_TRAP_FILE):
            msg = open(ZPOOL_TRAP_FILE).read()

            if msg == "":
                msg = "zpool device removal detected."

            return Alert(ZpoolTrapAlertClass, msg)
