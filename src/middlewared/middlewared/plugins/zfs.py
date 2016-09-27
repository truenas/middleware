from middlewared.service import CRUDService

import libzfs


class ZFSSnapshotService(CRUDService):

    class Config:
        namespace = 'zfs.snapshot'
        private = True

    def query(self, filters=None, options=None):
        zfs = libzfs.ZFS()
        for i in zfs.snapshots:
            yield i.__getstate__()
