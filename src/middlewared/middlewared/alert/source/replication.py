from middlewared.alert.base import Alert, AlertLevel, AlertSource


class ReplicationAlertSource(AlertSource):
    level = AlertLevel.CRITICAL
    title = "Replication failed"

    async def check(self):
        alerts = []
        for replication in await self.middleware.call("replication.query", [["enabled", "=", True]]):
            if replication["state"]["state"] == "ERROR":
                alerts.append(Alert(
                    "Replication %(replication)s failed: %(message)s",
                    {
                        "replication": "%s -> %s:%s" % (
                            ". ".join(replication["source_datasets"]),
                            (replication["ssh_credentials"] or {}).get("name", "localhost"),
                            replication["target_dataset"],
                        ),
                        "message": replication["state"]["error"],
                    },
                ))

        return alerts
