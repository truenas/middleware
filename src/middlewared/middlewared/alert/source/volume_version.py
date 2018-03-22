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
            if not self.is_upgraded(pool):
                alerts.append(Alert(
                    "New feature flags are available for volume %s. Refer "
                    "to the \"Upgrading a ZFS Pool\" section of the User "
                    "Guide for instructions.",
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

    def is_upgraded(self, pool):
        if not pool["is_decrypted"]:
            return True

        try:
            version = self.middleware.call_sync("notifier.zpool_version", pool["name"])
        except ValueError:
            return True

        if version == "-":
            proc = subprocess.Popen([
                "zpool",
                "get",
                "-H", "-o", "property,value",
                "all",
                pool["name"],
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf8")
            data = proc.communicate()[0].strip("\n")
            for line in data.split("\n"):
                if not line.startswith("feature") or "\t" not in line:
                    continue
                prop, value = line.split("\t", 1)
                if value not in ("active", "enabled"):
                    return False
            return True

        return False
