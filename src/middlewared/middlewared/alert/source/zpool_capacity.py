from datetime import timedelta
import subprocess

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource
from middlewared.alert.schedule import IntervalSchedule


class ZpoolCapacityWarningAlertClass(AlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.WARNING
    title = "The capacity for the volume is above 80%"
    text = (
        "The capacity for the volume \"%(volume)s\" is currently at "
        "%(capacity)d%%, while the recommended value is below 80%%."
    )


class ZpoolCapacityCriticalAlertClass(AlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.CRITICAL
    title = "The capacity for the volume is above 90%"
    text = (
        "The capacity for the volume \"%(volume)s\" is currently at "
        "%(capacity)d%%, while the recommended value is below 80%%."
    )


class ZpoolCapacityAlertSource(ThreadedAlertSource):
    schedule = IntervalSchedule(timedelta(minutes=5))

    def check_sync(self):
        alerts = []
        pools = [
            pool["name"]
            for pool in self.middleware.call_sync("pool.query")
        ] + ["freenas-boot"]
        for pool in pools:
            proc = subprocess.Popen([
                "/sbin/zpool",
                "list",
                "-H",
                "-o", "cap",
                pool.encode("utf8"),
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf8")
            data = proc.communicate()[0]
            if proc.returncode != 0:
                continue
            try:
                cap = int(data.strip("\n").replace("%", ""))
            except ValueError:
                continue

            klass = None
            if cap >= 90:
                klass = ZpoolCapacityWarningAlertClass
            elif cap >= 80:
                klass = ZpoolCapacityCriticalAlertClass
            if klass:
                alerts.append(
                    Alert(
                        klass,
                        {
                            "volume": pool,
                            "capacity": cap,
                        },
                        key=[pool],
                    )
                )

        return alerts
