from collections import defaultdict

from middlewared.schema import Dict, Int, Patch, returns
from middlewared.service import accepts, item_method, Service


class PeriodicSnapshotTaskService(Service):

    class Config:
        namespace = "pool.snapshottask"

    @item_method
    @accepts(
        Int("id"),
        Patch(
            "periodic_snapshot_create",
            "periodic_snapshot_update_will_change_retention",
            ("attr", {"update": True}),
        ),
    )
    @returns(Dict("snapshots", additional_attrs=True))
    async def update_will_change_retention_for(self, id, data):
        """
        Returns a list of snapshots which will change the retention if periodic snapshot task `id` is updated
        with `data`.
        """

        old = await self.middleware.call("pool.snapshottask.get_instance", id)
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
    @accepts(
        Int("id"),
    )
    @returns(Dict("snapshots", additional_attrs=True))
    async def delete_will_change_retention_for(self, id):
        """
        Returns a list of snapshots which will change the retention if periodic snapshot task `id` is deleted.
        """

        task = await self.middleware.call("pool.snapshottask.get_instance", id)

        result = defaultdict(list)
        snapshots = await self.middleware.call("zettarepl.periodic_snapshot_task_snapshots", task)
        for snapshot in sorted(snapshots):
            dataset, snapshot = snapshot.split("@", 1)
            result[dataset].append(snapshot)

        return result
