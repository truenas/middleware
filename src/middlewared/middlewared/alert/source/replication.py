from middlewared.alert.base import Alert, AlertLevel, AlertSource


class ReplicationAlertSource(AlertSource):
    level = AlertLevel.CRITICAL
    title = "Replication failed"

    async def check(self):
        alerts = []
        for replication in await self.middleware.call("datastore.query", "storage.replication",
                                                      [["repl_enabled", "=", True]]):
            message = replication["repl_lastresult"].get("msg")
            if message in ("Succeeded", "Up to date", "Waiting", "Running", "", None):
                continue

            alerts.append(Alert(
                "Replication %(replication)s failed: %(message)s",
                {
                    "replication": "%s -> %s:%s" % (
                        replication["repl_filesystem"],
                        replication["repl_remote"]["ssh_remote_hostname"],
                        replication["repl_zfs"],
                    ),
                    "message": message,
                },
            ))

        return alerts
