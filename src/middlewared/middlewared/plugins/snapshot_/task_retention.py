from collections import defaultdict

from middlewared.api import api_method
from middlewared.api.current import (
    PoolSnapshotTaskUpdateWillChangeRetentionForArgs, PoolSnapshotTaskUpdateWillChangeRetentionForResult,
    PoolSnapshotTaskDeleteWillChangeRetentionForArgs, PoolSnapshotTaskDeleteWillChangeRetentionForResult
)
from middlewared.service import item_method, Service


class PeriodicSnapshotTaskService(Service):

    class Config:
        namespace = "pool.snapshottask"

    @item_method
    @api_method(PoolSnapshotTaskUpdateWillChangeRetentionForArgs, PoolSnapshotTaskUpdateWillChangeRetentionForResult)
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

    @item_method
    @api_method(PoolSnapshotTaskDeleteWillChangeRetentionForArgs, PoolSnapshotTaskDeleteWillChangeRetentionForResult)
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
