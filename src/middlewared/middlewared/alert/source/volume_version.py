from datetime import timedelta
import subprocess

from middlewared.alert.base import Alert, AlertLevel, ThreadedAlertSource
from middlewared.alert.schedule import IntervalSchedule


class VolumeVersionAlertSource(ThreadedAlertSource):
    level = AlertLevel.WARNING
    title = "New Feature Flags Are Available for Pool"

    schedule = IntervalSchedule(timedelta(minutes=5))

    def check_sync(self):
        alerts = []
        for pool in self.middleware.call_sync("pool.query"):
            if not self.is_upgraded(pool):
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
                "ZFS filesystem version is out of date. Please consider upgrading it. See <a href=\""
                "https://www.ixsystems.com/documentation/freenas/11.2/install.html#upgrading-a-zfs-pool\">"
                "Upgrading a ZFS Pool</a> for details."
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
