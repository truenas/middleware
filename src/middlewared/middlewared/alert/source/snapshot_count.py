from collections import defaultdict

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
        datasets = defaultdict(lambda: 0)
        for snapshot in await self.middleware.call("zfs.snapshot.query", [], {"select": ["name"]}):
            total += 1
            datasets[snapshot["name"].split("@")[0]] += 1

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
