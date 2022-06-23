from pathlib import Path

from middlewared.plugins.zfs_.utils import ZFSCTL
from middlewared.schema import accepts, returns, Int, Str
from middlewared.service import Service


class PoolDatasetService(Service):

    class Config:
        namespace = "pool.dataset"

    @accepts(Str("dataset"))
    @returns(Int())
    def snapshot_count(self, dataset):
        if mountpoint := self.middleware.call_sync("pool.dataset.mountpoint", dataset, False):
            zfs_dir = Path(mountpoint) / ".zfs/snapshot"
            if zfs_dir.is_dir():
                stat = zfs_dir.stat()
                if stat.st_ino == ZFSCTL.INO_SNAPDIR:
                    return stat.st_nlink - 2

        return self.middleware.call_sync("zfs.snapshot.query", [["dataset", "=", dataset]], {"count": True})
