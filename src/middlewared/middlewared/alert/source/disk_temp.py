# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from middlewared.alert.base import (
    Alert,
    AlertCategory,
    AlertClass,
    AlertLevel,
    AlertSource,
)


class DiskTemperatureTooHotAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = "Disk Temperature Is Too Hot"
    text = (
        "Disk %(n)s (with serial: %(s)s) critical temperature"
        " threshold is %(t)d degrees celsius and the current temp is"
        " %(ct)d degrees celsius"
    )


class DiskTemperatureTooHotAlertSource(AlertSource):
    run_on_backup_node = False

    async def check(self):
        alerts = list()
        map = {i.name: i for i in await self.middleware.call("disk.get_disks")}
        temp_cache = await self.middleware.call("disk.temperatures", [], True)
        for disk, (temp, crit) in temp_cache.items():
            if temp is None or crit is None:
                continue
            elif temp < crit:
                continue

            try:
                di = map[disk]
            except KeyError:
                # We're checking a cache of disk temps
                # so disk could have gone away by the time
                # this alert runs
                continue
            else:
                alerts.append(
                    Alert(
                        DiskTemperatureTooHotAlertClass,
                        {"n": disk, "s": di.serial, "t": crit, "ct": temp},
                    )
                )
        return alerts
