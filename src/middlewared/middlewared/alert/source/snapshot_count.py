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
        "Dataset %(dataset)s has more snapshots (%(count)d) than recommended (%(max)d). Performance or functionality "
        "might degrade."
    )


class SnapshotCountAlertSource(AlertSource):
    schedule = CrontabSchedule(hour=1)
    run_on_backup_node = False

    async def check(self):
        max = await self.middleware.call("pool.snapshottask.max_count")
        max_total = await self.middleware.call("pool.snapshottask.max_total_count")

        total = 0
        datasets = await self.middleware.call("zfs.snapshot.count")

        for cnt in datasets.values():
            total += cnt

        if total > max_total:
            return Alert(
                SnapshotTotalCountAlertClass,
                {"count": total, "max": max_total},
                key=None,
            )

        for dataset in sorted(datasets.keys()):
            count = datasets[dataset]
            if count > max:
                return Alert(
                    SnapshotCountAlertClass,
                    {"dataset": dataset, "count": count, "max": max},
                    key=None,
                )
