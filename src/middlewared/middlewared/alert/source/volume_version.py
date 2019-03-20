from datetime import timedelta
import subprocess

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource
from middlewared.alert.schedule import IntervalSchedule


class VolumeVersionAlertClass(AlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.WARNING
    title = "New feature flags are available for volume"
    text = (
        "New feature flags are available for volume %s. Refer "
        "to the \"Upgrading a ZFS Pool\" subsection in the "
        "User Guide \"Installing and Upgrading\" chapter "
        "and \"Upgrading\" section for more instructions."
    )


class ZfsVersionOutOfDateAlertClass(AlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.WARNING
    title = "ZFS filesystem version is out of date"
    text = (
        "ZFS filesystem version is out of date. Consider upgrading "
        "using \"zfs upgrade\" command line."
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

        proc = subprocess.Popen(
            "zfs upgrade | grep FILESYSTEM",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf8",
        )
        output = proc.communicate()[0].strip(" ").strip("\n")
        if output:
            alerts.append(Alert(ZfsVersionOutOfDateAlertClass))

        return alerts
