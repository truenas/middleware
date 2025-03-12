from middlewared.api.current import PoolSnapshotEntry
from middlewared.service import CRUDService, filterable_api_method


class PoolSnapshotService(CRUDService):

    class Config:
        namespace = 'pool.snapshot'
        role_prefix = 'SNAPSHOT'
        entry = PoolSnapshotEntry

    def clone(self, data):
        return self.middleware.call_sync('zfs.snapshot.clone', data)

    def rollback(self, id_, options):
        return self.middleware.call_sync('zfs.snapshot.rollback', id_, options)

    def hold(self, id_, options):
        return self.middleware.call_sync('zfs.snapshot.hold', id_, options)

    def release(self, id_, options):
        return self.middleware.call_sync('zfs.snapshot.release', id_, options)

    @filterable_api_method(item=PoolSnapshotEntry)
    def query(self, filters, options):
        return self.middleware.call_sync('zfs.snapshot.query', filters, options)

    def do_create(self, data):
        return self.middleware.call_sync('zfs.snapshot.create', data)

    def do_delete(self, id_, options):
        return self.middleware.call_sync('zfs.snapshot.delete', id_, options)
