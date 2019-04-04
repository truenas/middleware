from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource


class ReplicationSuccessAlertClass(AlertClass):
    category = AlertCategory.TASKS
    level = AlertLevel.INFO
    title = "Replication Succeeded"
    text = "Replication \"%(name)s\" succeeded."


class ReplicationFailedAlertClass(AlertClass):
    category = AlertCategory.TASKS
    level = AlertLevel.CRITICAL
    title = "Replication Failed"
    text = "Replication \"%(name)s\" failed: %(message)s."


class ReplicationAlertSource(AlertSource):
    async def check(self):
        alerts = []
        for replication in await self.middleware.call("replication.query", [["enabled", "=", True]]):
            if replication["state"]["state"] == "FINISHED":
                alerts.append(
                    Alert(
                        ReplicationSuccessAlertClass,
                        {
                            "name": replication["name"],
                        },
                        key=[replication["state"]["datetime"].isoformat()],
                        datetime=replication["state"]["datetime"],
                    )
                )
            if replication["state"]["state"] == "ERROR":
                alerts.append(
                    Alert(
                        ReplicationSuccessAlertClass,
                        {
                            "name": replication["name"],
                            "message": replication["state"]["error"],
                        },
                        key=[replication["state"]["datetime"].isoformat()],
                        datetime=replication["state"]["datetime"],
                    )
                )

        return alerts
