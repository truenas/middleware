from dataclasses import dataclass
from typing import Any

from middlewared.alert.base import Alert, AlertCategory, AlertClass, AlertClassConfig, AlertLevel, AlertSource


@dataclass(kw_only=True)
class SnapshotFailedAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.TASKS,
        level=AlertLevel.CRITICAL,
        title="Snapshot Task Failed",
        text='Snapshot Task For Dataset "%(name)s" failed: %(message)s.',
    )

    name: str
    message: str
    id: int
    datetime_iso: str

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return [args["id"], args["datetime_iso"]]


@dataclass(kw_only=True)
class ReplicationSuccessAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.TASKS,
        level=AlertLevel.INFO,
        title="Replication Succeeded",
        text='Replication "%(name)s" succeeded.',
    )

    name: str
    id: int
    datetime_iso: str

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return [args["id"], args["datetime_iso"]]


@dataclass(kw_only=True)
class ReplicationFailedAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.TASKS,
        level=AlertLevel.CRITICAL,
        title="Replication Failed",
        text='Replication "%(name)s" failed: %(message)s.',
    )

    name: str
    message: str
    id: int
    datetime_iso: str

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return [args["id"], args["datetime_iso"]]


class ReplicationAlertSource(AlertSource):
    async def check(self) -> list[Alert[Any]]:
        alerts: list[Alert[Any]] = []
        snapshottasks = await self.middleware.call2(
            self.middleware.services.pool.snapshottask.query, [["enabled", "=", True]],
        )
        assert isinstance(snapshottasks, list)
        for snapshottask in snapshottasks:
            if snapshottask.state["state"] == "ERROR":
                alerts.append(
                    Alert(
                        SnapshotFailedAlert(
                            name=snapshottask.dataset,
                            message=snapshottask.state["error"],
                            id=snapshottask.id,
                            datetime_iso=snapshottask.state["datetime"].isoformat(),
                        ),
                        datetime=snapshottask.state["datetime"],
                    )
                )

        for replication in await self.middleware.call("replication.query", [["enabled", "=", True]]):
            if replication["state"]["state"] == "FINISHED":
                alerts.append(
                    Alert(
                        ReplicationSuccessAlert(
                            name=replication["name"],
                            id=replication["id"],
                            datetime_iso=replication["state"]["datetime"].isoformat(),
                        ),
                        datetime=replication["state"]["datetime"],
                    )
                )
            if replication["state"]["state"] == "ERROR":
                alerts.append(
                    Alert(
                        ReplicationFailedAlert(
                            name=replication["name"],
                            message=replication["state"]["error"],
                            id=replication["id"],
                            datetime_iso=replication["state"]["datetime"].isoformat(),
                        ),
                        datetime=replication["state"]["datetime"],
                    )
                )

        return alerts
