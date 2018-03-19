# Copyright (c) 2015 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

import os

from middlewared.alert.base import Alert, AlertLevel, AlertSource


class ZpoolTrapAlertSource(AlertSource):
    level = AlertLevel.CRITICAL
    title = "zpool device removal detected"

    async def check(self):
        ZPOOL_TRAP_FILE = "/var/tmp/zpool_trap"
        if os.path.exists(ZPOOL_TRAP_FILE):
            msg = open(ZPOOL_TRAP_FILE).read()

            if msg == "":
                return Alert()
            else:
                return Alert(msg)
