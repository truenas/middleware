from collections import defaultdict

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource
from middlewared.alert.schedule import CrontabSchedule


class SnapshotCountAlertClass(AlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.WARNING
    title = "Too Many Snapshots Exist"
    text = (
        "Dataset %(dataset)s has more snapshots (%(count)d) than recommended (%(max)d). Performance or functionality "
        "might degrade."
    )


class SnapshotCountAlertSource(AlertSource):
    schedule = CrontabSchedule(hour=1)
    run_on_backup_node = False

    async def check(self):
        max = await self.middleware.call("pool.snapshottask.max_count")

        datasets = defaultdict(lambda: 0)
        for snapshot in await self.middleware.call("zfs.snapshot.query", [], {"select": ["name"]}):
            datasets[snapshot["name"].split("@")[0]] += 1

        for dataset in sorted(datasets.keys()):
            count = datasets[dataset]
            if count > max:
                return Alert(
                    SnapshotCountAlertClass,
                    {"dataset": dataset, "count": count, "max": max},
                    key=None,
                )
