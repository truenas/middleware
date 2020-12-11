from datetime import timedelta
import subprocess

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource
from middlewared.alert.schedule import IntervalSchedule


class ZpoolCapacityWarningAlertClass(AlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.WARNING
    title = "Pool Space Usage Is Above 80%"
    text = (
        "Space usage for pool \"%(volume)s\" is %(capacity)d%%. "
        "Optimal pool performance requires used space remain below 80%%."
    )


class ZpoolCapacityCriticalAlertClass(AlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.CRITICAL
    title = "Pool Space Usage Is Above 90%"
    text = (
        "Space usage for pool \"%(volume)s\" is %(capacity)d%%. "
        "Optimal pool performance requires used space remain below 80%%."
    )


class ZpoolCapacityAlertSource(ThreadedAlertSource):
    schedule = IntervalSchedule(timedelta(minutes=5))

    def check_sync(self):
        alerts = []
        pools = [
            pool["name"]
            for pool in self.middleware.call_sync("pool.query")
        ] + [self.middleware.call_sync("boot.pool_name")]
        for pool in pools:
            proc = subprocess.Popen([
                "zpool",
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
                klass = ZpoolCapacityCriticalAlertClass
            elif cap >= 80:
                klass = ZpoolCapacityWarningAlertClass
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
