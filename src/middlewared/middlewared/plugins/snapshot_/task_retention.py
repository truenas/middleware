from collections import defaultdict

from middlewared.api import api_method
from middlewared.api.current import (
    PeriodicSnapshotTaskUpdateWillChangeRetentionForArgs, PeriodicSnapshotTaskUpdateWillChangeRetentionForResult,
    PeriodicSnapshotTaskDeleteWillChangeRetentionForArgs, PeriodicSnapshotTaskDeleteWillChangeRetentionForResult
)
from middlewared.service import Service


class PeriodicSnapshotTaskService(Service):

    class Config:
        namespace = "pool.snapshottask"

    @api_method(PeriodicSnapshotTaskUpdateWillChangeRetentionForArgs, PeriodicSnapshotTaskUpdateWillChangeRetentionForResult,
		roles=['SNAPSHOT_TASK_READ'])
    async def update_will_change_retention_for(self, id_, data):
        """
        Returns a list of snapshots which will change the retention if periodic snapshot task `id` is updated
        with `data`.
        """

        old = await self.middleware.call("pool.snapshottask.get_instance", id_)
        new = dict(old, **data)

        result = defaultdict(list)
        if old != new:
            old_snapshots = await self.middleware.call("zettarepl.periodic_snapshot_task_snapshots", old)
            new_snapshots = await self.middleware.call("zettarepl.periodic_snapshot_task_snapshots", new)
            if diff := old_snapshots - new_snapshots:
                for snapshot in sorted(diff):
                    dataset, snapshot = snapshot.split("@", 1)
                    result[dataset].append(snapshot)

        return result

    @api_method(PeriodicSnapshotTaskDeleteWillChangeRetentionForArgs, PeriodicSnapshotTaskDeleteWillChangeRetentionForResult,
		roles=['SNAPSHOT_TASK_READ'])
    async def delete_will_change_retention_for(self, id_):
        """
        Returns a list of snapshots which will change the retention if periodic snapshot task `id` is deleted.
        """

        task = await self.middleware.call("pool.snapshottask.get_instance", id_)

        result = defaultdict(list)
        snapshots = await self.middleware.call("zettarepl.periodic_snapshot_task_snapshots", task)
        for snapshot in sorted(snapshots):
            dataset, snapshot = snapshot.split("@", 1)
            result[dataset].append(snapshot)

        return result
