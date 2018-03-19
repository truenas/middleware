# Copyright (c) 2015 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

from middlewared.alert.base import Alert, AlertLevel, AlertSource


class SystemDatasetAlertSource(AlertSource):
    level = AlertLevel.WARNING
    title = 'System dataset is recommended to be set to freenas-boot pool.'

    async def check(self):
        sysds = await self.middleware.call("datastore.query", "system.systemdataset")
        if not sysds:
            return
        sysds = sysds[0]
        if sysds["sys_pool"] != 'freenas-boot':
            return Alert()
