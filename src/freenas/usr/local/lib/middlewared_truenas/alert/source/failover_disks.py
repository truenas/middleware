# Copyright (c) 2018 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.
from middlewared.alert.base import Alert, AlertLevel, AlertSource


class FailoverDisksAlertSource(AlertSource):
    level = AlertLevel.CRITICAL
    title = "Disks on backup node do not match disks on master node"

    run_on_backup_node = False

    async def check(self):
        alerts = []

        if not await self.middleware.call("failover.licensed"):
            return alerts

        local_disks = set((await self.middleware.call("device.get_info", "DISK")).keys())
        remote_disks = set((await self.middleware.call("failover.call_remote", "device.get_info", ["DISK"])).keys())

        if local_disks - remote_disks:
            alerts.append(Alert(title="The following disks are not present on backup node: %(disks)s",
                                args={"disks": ", ".join(sorted(local_disks - remote_disks))}))

        if remote_disks - local_disks:
            alerts.append(Alert(title="The following disks are not present on master node: %(disks)s",
                                args={"disks": ", ".join(sorted(remote_disks - local_disks))}))

        return alerts
