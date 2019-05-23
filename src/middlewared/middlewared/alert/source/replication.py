from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource


class SnapshotFailedAlertClass(AlertClass):
    category = AlertCategory.TASKS
    level = AlertLevel.CRITICAL
    title = "Snapshot Task Failed"
    text = "Snapshot Task For Dataset \"%(name)s\" failed: %(message)s."


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
        for snapshottask in await self.middleware.call("pool.snapshottask.query", [["enabled", "=", True]]):
            if snapshottask["state"]["state"] == "ERROR":
                alerts.append(
                    Alert(
                        SnapshotFailedAlertClass,
                        {
                            "name": snapshottask["dataset"],
                            "message": snapshottask["state"]["error"],
                        },
                        key=[snapshottask["id"], snapshottask["state"]["datetime"].isoformat()],
                        datetime=snapshottask["state"]["datetime"],
                    )
                )

        for replication in await self.middleware.call("replication.query", [["enabled", "=", True]]):
            if replication["state"]["state"] == "FINISHED":
                alerts.append(
                    Alert(
                        ReplicationSuccessAlertClass,
                        {
                            "name": replication["name"],
                        },
                        key=[replication["id"], replication["state"]["datetime"].isoformat()],
                        datetime=replication["state"]["datetime"],
                    )
                )
            if replication["state"]["state"] == "ERROR":
                alerts.append(
                    Alert(
                        ReplicationFailedAlertClass,
                        {
                            "name": replication["name"],
                            "message": replication["state"]["error"],
                        },
                        key=[replication["id"], replication["state"]["datetime"].isoformat()],
                        datetime=replication["state"]["datetime"],
                    )
                )

        return alerts
