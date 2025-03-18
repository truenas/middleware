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
        cli_namespace = 'storage.snapshot'
        role_prefix = 'SNAPSHOT'
        role_separate_delete = True
        event_send = False  # Don't send events implicitly.
        entry = PoolSnapshotEntry

    @api_method(PoolSnapshotCloneArgs, PoolSnapshotCloneResult, roles=['SNAPSHOT_WRITE', 'DATASET_WRITE'])
    def clone(self, data):
        """Clone a given snapshot to a new dataset."""
        return self.middleware.call_sync('zfs.snapshot.clone', data)

    @api_method(PoolSnapshotRollbackArgs, PoolSnapshotRollbackResult, roles=['SNAPSHOT_WRITE', 'POOL_WRITE'])
    def rollback(self, id_, options):
        return self.middleware.call_sync('zfs.snapshot.rollback', id_, options)

    @api_method(PoolSnapshotHoldArgs, PoolSnapshotHoldResult, roles=['SNAPSHOT_WRITE'])
    def hold(self, id_, options):
        """Hold snapshot `id`.

        Add `truenas` tag to the snapshot's tag namespace.

        """
        return self.middleware.call_sync('zfs.snapshot.hold', id_, options)

    @api_method(PoolSnapshotReleaseArgs, PoolSnapshotReleaseResult, roles=['SNAPSHOT_WRITE'])
    def release(self, id_, options):
        """Release hold on snapshot `id`.

        Remove all hold tags from the specified snapshot.

        """
        return self.middleware.call_sync('zfs.snapshot.release', id_, options)

    @filterable_api_method(item=PoolSnapshotEntry)
    def query(self, filters, options):
        """Query all ZFS Snapshots with `query-filters` and `query-options`.

        `query-options.extra.holds` *(bool)*
            Include hold tags for snapshots in the query result (false by default).
        `query-options.extra.min_txg` *(int)*
            Limit snapshot retrieval based on minimum transaction group.
        `query-options.extra.max_txg` *(int)*
            Limit snapshot retrieval based on maximum transaction group.
        `query-options.extra.retention` *(bool)*
            Include retention information in the query result (false by default).
        `query-options.extra.properties` *(dict)*
            Passed to `zfs.snapshots_serialized.props`.

        """
        return self.middleware.call_sync('zfs.snapshot.query', filters, options)

    @api_method(PoolSnapshotCreateArgs, PoolSnapshotCreateResult)
    def do_create(self, data):
        """Take a snapshot from a given dataset."""
        result = self.middleware.call_sync('zfs.snapshot.create', data)
        self.middleware.send_event(f'{self._config.namespace}.query', 'ADDED', id=result['id'], fields=result)
        return result

    @api_method(PoolSnapshotUpdateArgs, PoolSnapshotUpdateResult)
    def do_update(self, snap_id, data):
        data['user_properties_update'].extend({'key': k, 'remove': True} for k in data.pop('user_properties_remove'))
        return self.middleware.call_sync('zfs.snapshot.update', snap_id, data)

    @api_method(PoolSnapshotDeleteArgs, PoolSnapshotDeleteResult)
    def do_delete(self, id_, options):
        result = self.middleware.call_sync('zfs.snapshot.delete', id_, options)
        self.middleware.send_event(
            f'{self._config.namespace}.query',
            'REMOVED',
            id=id_,
            recursive=options['recursive']
        )  # TODO: Events won't be sent for child snapshots in recursive delete
        return result
