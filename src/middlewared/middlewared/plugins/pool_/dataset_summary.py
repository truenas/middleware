from middlewared.schema import accepts, returns, Dict, Int, Str
from middlewared.service import Service


class PoolDatasetService(Service):

    class Config:
        namespace = "pool.dataset"

    @accepts(Str("dataset"))
    @returns(Dict(
        Int("cloud_sync_task_count"),
        Int("replication_task_count"),
        Int("rsync_task_count"),
        Int("snapshot_count"),
        Int("snapshot_task_count"),
    ))
    async def summary(self, dataset):
        path = f"/mnt/{dataset}"

        return {
            "cloud_sync_task_count": len(await self.middleware.call("pool.dataset.query_attachment_delegate",
                                                                    "cloudsync", path, True)),
            "replication_task_count": len(await self.middleware.call("pool.dataset.query_attachment_delegate",
                                                                     "replication", path, True)),
            "rsync_task_count": len(await self.middleware.call("pool.dataset.query_attachment_delegate",
                                                               "rsync", path, True)),
            "snapshot_count": await self.middleware.call("pool.dataset.snapshot_count", dataset),
            "snapshot_task_count": len(await self.middleware.call("pool.dataset.query_attachment_delegate",
                                                                  "snapshottask", path, True)),
        }
