from middlewared.alert.base import AlertClass, AlertClassConfig, AlertCategory, AlertLevel, Alert, AlertSource


class SnapshotFailedAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.TASKS,
        level=AlertLevel.CRITICAL,
        title="Snapshot Task Failed",
        text="Snapshot Task For Dataset \"%(name)s\" failed: %(message)s.",
    )


class ReplicationSuccessAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.TASKS,
        level=AlertLevel.INFO,
        title="Replication Succeeded",
        text="Replication \"%(name)s\" succeeded.",
    )


class ReplicationFailedAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.TASKS,
        level=AlertLevel.CRITICAL,
        title="Replication Failed",
        text="Replication \"%(name)s\" failed: %(message)s.",
    )


class ReplicationAlertSource(AlertSource):
    async def check(self):
        alerts = []
        for snapshottask in await self.middleware.call2(
            self.middleware.services.pool.snapshottask.query, [["enabled", "=", True]],
        ):
            if snapshottask.state["state"] == "ERROR":
                alerts.append(
                    Alert(
                        SnapshotFailedAlert,
                        {
                            "name": snapshottask.dataset,
                            "message": snapshottask.state["error"],
                        },
                        key=[snapshottask.id, snapshottask.state["datetime"].isoformat()],
                        datetime=snapshottask.state["datetime"],
                    )
                )

        for replication in await self.middleware.call("replication.query", [["enabled", "=", True]]):
            if replication["state"]["state"] == "FINISHED":
                alerts.append(
                    Alert(
                        ReplicationSuccessAlert,
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
                        ReplicationFailedAlert,
                        {
                            "name": replication["name"],
                            "message": replication["state"]["error"],
                        },
                        key=[replication["id"], replication["state"]["datetime"].isoformat()],
                        datetime=replication["state"]["datetime"],
                    )
                )

        return alerts
