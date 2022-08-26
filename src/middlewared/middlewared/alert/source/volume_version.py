from datetime import timedelta

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource
from middlewared.alert.schedule import IntervalSchedule


class VolumeVersionAlertClass(AlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.WARNING
    title = "New Feature Flags Are Available for Pool"
    text = (
        "New ZFS version or feature flags are available for pool(s) %s. Upgrading pools is a one-time process that can "
        "prevent rolling the system back to an earlier TrueNAS version. It is recommended to read the TrueNAS release "
        "notes and confirm you need the new ZFS feature flags before upgrading a pool."
    )


class VolumeVersionAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(minutes=5))
    run_on_backup_node = False

    async def check(self):
        pools_needing_upgrade = []
        for pool in await self.middleware.call("pool.query"):
            if not await self.middleware.call("pool.is_upgraded", pool["id"]):
                pools_needing_upgrade.append(pool["name"])

        if pools_needing_upgrade:
            return Alert(VolumeVersionAlertClass, ', '.join(pools_needing_upgrade))
