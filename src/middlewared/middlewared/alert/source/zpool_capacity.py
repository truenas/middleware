from datetime import timedelta
import subprocess

from middlewared.alert.base import Alert, AlertLevel, ThreadedAlertSource
from middlewared.alert.schedule import IntervalSchedule


class ZpoolCapacityAlertSource(ThreadedAlertSource):
    level = AlertLevel.WARNING
    title = "The capacity for the volume is above recommended value"

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

            msg = (
                "The capacity for the volume \"%(volume)s\" is currently at "
                "%(capacity)d%%, while the recommended value is below 80%%."
            )
            level = None
            if cap >= 90:
                level = AlertLevel.CRITICAL
            elif cap >= 80:
                level = AlertLevel.WARNING
            if level:
                alerts.append(
                    Alert(
                        msg,
                        {
                            "volume": pool,
                            "capacity": cap,
                        },
                        key=[pool, level.name],
                        level=level,
                    )
                )

        return alerts
