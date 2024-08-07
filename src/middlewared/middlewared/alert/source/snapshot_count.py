from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource
from middlewared.alert.schedule import CrontabSchedule


class SnapshotTotalCountAlertClass(AlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.WARNING
    title = "Too Many Snapshots Exist"
    text = (
        "Your system has more snapshots (%(count)d) than recommended (%(max)d). Performance or functionality "
        "might degrade."
    )


class SnapshotCountAlertClass(AlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.WARNING
    title = "Too Many Snapshots Exist For Dataset"
    text = (
        "SMB share %(dataset)s has more snapshots (%(count)d) than recommended (%(max)d). File Explorer may not "
        "display all snapshots in the Previous Versions tab."
    )


class SnapshotCountAlertSource(AlertSource):
    schedule = CrontabSchedule(hour=1)
    run_on_backup_node = False

    async def _check_total(self) -> Alert | None:
        """Return an `Alert` if the total number of snapshots exceeds the limit."""
        max_total = await self.middleware.call("pool.snapshottask.max_total_count")
        datasets = await self.middleware.call("zfs.snapshot.count")
        total = 0

        for cnt in datasets.values():
            total += cnt

        if total > max_total:
            return Alert(
                SnapshotTotalCountAlertClass,
                {"count": total, "max": max_total},
                key=None,
            )

    async def _check_smb(self) -> list[Alert]:
        """Return an `Alert` for every dataset shared over smb whose number of snapshots exceeds the limit."""
        max_ = await self.middleware.call("pool.snapshottask.max_count")
        datasets = await self.middleware.call("zfs.snapshot.count")
        smb_shares = await self.middleware.call("sharing.smb.query")
        smb_paths = [share["path"].removeprefix("/mnt/") for share in smb_shares]
        to_alert = list()

        for path in sorted(smb_paths):
            if path in datasets:
                count = datasets[path]
                if count > max_:
                    to_alert.append(Alert(
                        SnapshotCountAlertClass,
                        {"dataset": path, "count": count, "max": max_},
                        key=None,
                    ))

        return to_alert

    async def check(self):
        alerts = await self._check_smb()
        if total_alert := await self._check_total():
            alerts.append(total_alert)
        return alerts or None
