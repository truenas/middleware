from datetime import timedelta

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource
from middlewared.alert.schedule import IntervalSchedule


class VolumeVersionAlertClass(AlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.WARNING
    title = "New Feature Flags Are Available for Pool"
    text = (
        "New ZFS version or feature flags are available for pool %s. Upgrading pools is a one-time process that can "
        "prevent rolling the system back to an earlier TrueNAS version. It is recommended to read the TrueNAS release "
        "notes and confirm you need the new ZFS feature flags before upgrading a pool."
    )


class VolumeVersionAlertSource(ThreadedAlertSource):
    schedule = IntervalSchedule(timedelta(minutes=5))

    def check_sync(self):
        alerts = []
        for pool in self.middleware.call_sync("pool.query"):
            if not self.middleware.call_sync('pool.is_upgraded', pool["id"]):
                alerts.append(Alert(
                    VolumeVersionAlertClass,
                    pool["name"],
                ))

        return alerts
