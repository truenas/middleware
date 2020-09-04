from datetime import timedelta

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource
from middlewared.alert.schedule import IntervalSchedule


class VolumeVersionAlertClass(AlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.WARNING
    title = "New Feature Flags Are Available for Pool"
    text = (
        "New ZFS version or feature flags are available for pool %s. Please see <a href=\""
        "https://www.truenas.com/docs/hub/tasks/advanced/upgrading-pool/\">"
        "Upgrading a ZFS Pool</a> for details."
    )


class VolumeVersionAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(minutes=5))

    async def check(self):
        alerts = []
        for pool in await self.middleware.call("pool.query"):
            if not await self.middleware.call("pool.is_upgraded", pool["id"]):
                alerts.append(Alert(
                    VolumeVersionAlertClass,
                    pool["name"],
                ))

        return alerts
