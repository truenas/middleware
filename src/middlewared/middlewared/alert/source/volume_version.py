from datetime import timedelta
import subprocess

from middlewared.alert.base import Alert, AlertLevel, ThreadedAlertSource
from middlewared.alert.schedule import IntervalSchedule


class VolumeVersionAlertSource(ThreadedAlertSource):
    level = AlertLevel.WARNING
    title = "ZFS version is out of date"

    schedule = IntervalSchedule(timedelta(minutes=5))

    def check_sync(self):
        alerts = []
        for pool in self.middleware.call_sync("pool.query"):
            if not self.middleware.call_sync('pool.is_upgraded', pool["id"]):
                alerts.append(Alert(
                    "New feature flags are available for volume %s. Refer "
                    "to the \"Upgrading a ZFS Pool\" subsection in the "
                    "User Guide \"Installing and Upgrading\" chapter "
                    "and \"Upgrading\" section for more instructions.",
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
            alerts.append(Alert(
                "ZFS filesystem version is out of date. Consider upgrading"
                " using \"zfs upgrade\" command line."
            ))

        return alerts
