import errno

from middlewared.api import api_method
from middlewared.api.current import (
    PoolDatasetSnapshotCountArgs,
    PoolDatasetSnapshotCountResult,
    ZFSResourceSnapshotCountQuery,
)
from middlewared.service import Service
from middlewared.service_exception import ValidationError


class PoolDatasetService(Service):
    class Config:
        namespace = "pool.dataset"

    @api_method(
        PoolDatasetSnapshotCountArgs,
        PoolDatasetSnapshotCountResult,
        roles=["DATASET_READ"],
        check_annotations=True,
    )
    def snapshot_count(self, dataset: str) -> int:
        """Returns snapshot count for specified ``dataset``."""
        counts = self.call_sync2(self.s.zfs.resource.snapshot.count, ZFSResourceSnapshotCountQuery(paths=[dataset]))
        if not counts:
            raise ValidationError("zfs.resource.snapshot.count", f"{dataset!r} not found", errno.ENOENT)
        return counts.get(dataset, 0)
