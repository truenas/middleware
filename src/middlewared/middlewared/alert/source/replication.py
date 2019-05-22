from middlewared.alert.base import Alert, AlertLevel, AlertSource


class ReplicationAlertSource(AlertSource):
    level = AlertLevel.CRITICAL
    title = "Replication Failed"

    async def check(self):
        alerts = []
        for replication in await self.middleware.call("replication.query", [["enabled", "=", True]]):
            message = replication["lastresult"].get("msg")
            if message in ("Succeeded", "Up to date", "Waiting", "Running", "", None):
                continue

            alerts.append(Alert(
                "Replication %(replication)s failed: %(message)s",
                {
                    "replication": "%s -> %s:%s" % (
                        replication["filesystem"],
                        replication["remote_hostname"],
                        replication["zfs"],
                    ),
                    "message": message,
                },
            ))

        return alerts
