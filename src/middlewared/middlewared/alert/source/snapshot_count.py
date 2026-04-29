from dataclasses import dataclass
from typing import Any

from middlewared.alert.base import Alert, AlertCategory, AlertClass, AlertClassConfig, AlertLevel, AlertSource
from middlewared.alert.schedule import CrontabSchedule
from middlewared.api.current import ZFSResourceSnapshotCountQuery
from middlewared.utils.path import FSLocation, path_location


@dataclass(kw_only=True)
class SnapshotTotalCountAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.STORAGE,
        level=AlertLevel.WARNING,
        title="Too Many Snapshots Exist",
        text=(
            "Your system has more snapshots (%(count)d) than recommended (%(max)d). Performance or functionality "
            "might degrade."
        ),
    )

    count: int
    max: int

    @classmethod
    def key_from_args(cls, args: Any) -> None:
        return None


@dataclass(kw_only=True)
class SnapshotCountAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.STORAGE,
        level=AlertLevel.WARNING,
        title="Too Many Snapshots Exist For Dataset",
        text=(
            "SMB share %(dataset)s has more snapshots (%(count)d) than recommended (%(max)d). File Explorer may not "
            "display all snapshots in the Previous Versions tab."
        ),
    )

    dataset: str
    count: int
    max: int

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return args["dataset"]


class SnapshotCountAlertSource(AlertSource):
    schedule = CrontabSchedule(hour=1)
    run_on_backup_node = False

    async def _check_total(self, snapshot_counts: dict[str, int]) -> list[Alert[Any]]:
        """Return an `Alert` if the total number of snapshots exceeds the limit."""
        max_total = await self.middleware.call2(self.middleware.services.pool.snapshottask.max_total_count)
        total = sum(snapshot_counts.values())

        if total > max_total:
            return [Alert(SnapshotTotalCountAlert(
                count=total,
                max=max_total,
            ))]

        return []

    async def _check_smb(self, snapshot_counts: dict[str, int]) -> list[Alert[Any]]:
        """Return an `Alert` for every dataset shared over smb whose number of snapshots exceeds the limit."""
        max_ = await self.middleware.call2(self.middleware.services.pool.snapshottask.max_count)
        to_alert = list()

        for share in await self.middleware.call("sharing.smb.query"):
            if path_location(share["path"]) != FSLocation.LOCAL:
                continue
            path = share["path"].removeprefix("/mnt/")
            count = snapshot_counts.get(path, 0)
            if count > max_:
                to_alert.append(Alert(SnapshotCountAlert(
                    dataset=path,
                    count=count,
                    max=max_,
                )))

        return to_alert

    async def check(self) -> list[Alert[Any]]:
        snapshot_counts = await self.middleware.call2(
            self.middleware.services.zfs.resource.snapshot.count_impl, ZFSResourceSnapshotCountQuery(recursive=True),
        )
        alerts = await self._check_smb(snapshot_counts)
        alerts.extend(await self._check_total(snapshot_counts))
        return alerts
