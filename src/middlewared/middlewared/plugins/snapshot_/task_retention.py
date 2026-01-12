from collections import defaultdict

from middlewared.api import api_method
from middlewared.api.current import (
    PeriodicSnapshotTaskUpdateWillChangeRetentionForArgs, PeriodicSnapshotTaskUpdateWillChangeRetentionForResult,
    PeriodicSnapshotTaskDeleteWillChangeRetentionForArgs, PeriodicSnapshotTaskDeleteWillChangeRetentionForResult,
    PeriodicSnapshotTaskEntry, PoolSnapshotTaskUpdateWillChangeRetentionFor,
)
from middlewared.service import Service


class PeriodicSnapshotTaskService(Service):

    class Config:
        namespace = "pool.snapshottask"

    @api_method(
        PeriodicSnapshotTaskUpdateWillChangeRetentionForArgs,
        PeriodicSnapshotTaskUpdateWillChangeRetentionForResult,
		roles=['SNAPSHOT_TASK_READ'],
        check_annotations=True,
    )
    async def update_will_change_retention_for(
        self,
        id_: int,
        data: PoolSnapshotTaskUpdateWillChangeRetentionFor
    ) -> dict[str, list[str]]:
        """
        Returns a list of snapshots which will change the retention if periodic snapshot task `id` is updated
        with `data`.
        """

        old = PeriodicSnapshotTaskEntry(**await self.call2(self.s.pool.snapshottask.get_instance, id_))
        new = old.updated(data)

        result = defaultdict(list)
        if old != new:
            old_snapshots = await self.middleware.call("zettarepl.periodic_snapshot_task_snapshots", old.model_dump())
            new_snapshots = await self.middleware.call("zettarepl.periodic_snapshot_task_snapshots", new.model_dump())
            if diff := old_snapshots - new_snapshots:
                for snapshot in sorted(diff):
                    dataset, snapshot = snapshot.split("@", 1)
                    result[dataset].append(snapshot)

        return result

    @api_method(
        PeriodicSnapshotTaskDeleteWillChangeRetentionForArgs,
        PeriodicSnapshotTaskDeleteWillChangeRetentionForResult,
		roles=['SNAPSHOT_TASK_READ'],
        check_annotations=True,
    )
    async def delete_will_change_retention_for(self, id_: int) -> dict[str, list[str]]:
        """
        Returns a list of snapshots which will change the retention if periodic snapshot task `id` is deleted.
        """

        task = await self.call2(self.s.pool.snapshottask.get_instance, id_)

        result = defaultdict(list)
        snapshots = await self.middleware.call("zettarepl.periodic_snapshot_task_snapshots", task)
        for snapshot in sorted(snapshots):
            dataset, snapshot = snapshot.split("@", 1)
            result[dataset].append(snapshot)

        return result
