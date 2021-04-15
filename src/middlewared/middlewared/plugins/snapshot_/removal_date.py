import hashlib

from middlewared.service import Service, job, private


class PeriodicSnapshotTaskService(Service):

    class Config:
        namespace = "pool.snapshottask"

    @private
    async def removal_date_property(self):
        host_id = await self.middleware.call("system.host_id")
        return f"org.truenas:destroy_at_{host_id[:8]}"

    @private
    @job(
        # Lock by pool name
        lock=lambda args: "pool.snapshottask.fixate_removal_date:" + (list(args[0].keys()) + ['-'])[0].split('/')[0],
    )
    async def fixate_removal_date(self, job, datasets, task):
        await self.middleware.call("zettarepl.fixate_removal_date", datasets, task)

