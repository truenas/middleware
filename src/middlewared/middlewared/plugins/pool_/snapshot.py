from middlewared.api import api_method
from middlewared.api.current import (
    PoolSnapshotEntry, PoolSnapshotCloneArgs, PoolSnapshotCloneResult, PoolSnapshotCreateArgs,
    PoolSnapshotCreateResult, PoolSnapshotDeleteArgs, PoolSnapshotDeleteResult, PoolSnapshotHoldArgs,
    PoolSnapshotHoldResult, PoolSnapshotReleaseArgs, PoolSnapshotReleaseResult, PoolSnapshotRollbackArgs,
    PoolSnapshotRollbackResult, PoolSnapshotUpdateArgs, PoolSnapshotUpdateResult
)
from middlewared.service import CRUDService, filterable_api_method


class PoolSnapshotService(CRUDService):

    class Config:
        namespace = 'pool.snapshot'
        role_prefix = 'SNAPSHOT'
        entry = PoolSnapshotEntry

    @api_method(PoolSnapshotCloneArgs, PoolSnapshotCloneResult, roles=['SNAPSHOT_WRITE', 'DATASET_WRITE'])
    def clone(self, data):
        return self.middleware.call_sync('zfs.snapshot.clone', data)

    @api_method(PoolSnapshotRollbackArgs, PoolSnapshotRollbackResult, roles=['SNAPSHOT_READ', 'POOL_WRITE'])
    def rollback(self, id_, options):
        return self.middleware.call_sync('zfs.snapshot.rollback', id_, options)

    @api_method(PoolSnapshotHoldArgs, PoolSnapshotHoldResult, roles=['SNAPSHOT_WRITE'])
    def hold(self, id_, options):
        return self.middleware.call_sync('zfs.snapshot.hold', id_, options)

    @api_method(PoolSnapshotReleaseArgs, PoolSnapshotReleaseResult, roles=['SNAPSHOT_WRITE'])
    def release(self, id_, options):
        return self.middleware.call_sync('zfs.snapshot.release', id_, options)

    @filterable_api_method(item=PoolSnapshotEntry)
    def query(self, filters, options):
        return self.middleware.call_sync('zfs.snapshot.query', filters, options)

    @api_method(PoolSnapshotCreateArgs, PoolSnapshotCreateResult)
    def do_create(self, data):
        return self.middleware.call_sync('zfs.snapshot.create', data)

    @api_method(PoolSnapshotUpdateArgs, PoolSnapshotUpdateResult)
    def do_update(self, snap_id, data):
        data['user_properties_update'].extend({'key': k, 'remove': True} for k in data.pop('user_properties_remove'))
        return self.middleware.call_sync('zfs.snapshot.update', snap_id, data)

    @api_method(PoolSnapshotDeleteArgs, PoolSnapshotDeleteResult)
    def do_delete(self, id_, options):
        return self.middleware.call_sync('zfs.snapshot.delete', id_, options)
