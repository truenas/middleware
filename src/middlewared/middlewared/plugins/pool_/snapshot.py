from middlewared.api import api_method
from middlewared.api.current import (
    PoolSnapshotEntry, PoolSnapshotCloneArgs, PoolSnapshotCloneResult, PoolSnapshotCreateArgs,
    PoolSnapshotCreateResult, PoolSnapshotDeleteArgs, PoolSnapshotDeleteResult, PoolSnapshotHoldArgs,
    PoolSnapshotHoldResult, PoolSnapshotReleaseArgs, PoolSnapshotReleaseResult, PoolSnapshotRollbackArgs,
    PoolSnapshotRollbackResult, PoolSnapshotUpdateArgs, PoolSnapshotUpdateResult, PoolSnapshotRenameArgs,
    PoolSnapshotRenameResult,
)
from middlewared.service import CRUDService, filterable_api_method, ValidationError
from middlewared.plugins.zfs.mount_unmount_impl import MountArgs
from middlewared.plugins.zfs.rename_promote_clone_impl import CloneArgs, RenameArgs


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
        self.middleware.call_sync(
            'zfs.resource.clone',
            CloneArgs(
                current_name=data['snapshot'],
                new_name=data['dataset_dst'],
                properties=data['dataset_properties'],
            )
        )
        self.middleware.call_sync(
            'zfs.resource.mount', MountArgs(filesystem=data['dataset_dst'])
        )
        return True

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

    @api_method(
        PoolSnapshotRenameArgs,
        PoolSnapshotRenameResult,
        audit='Pool snapshot rename from',
        audit_extended=lambda id_, new_name: f'{id_!r} to {new_name!r}',
        roles=['SNAPSHOT_WRITE']
    )
    async def rename(self, id_, options):
        """
        Rename a snapshot `id` to `new_name`.

        No safety checks are performed when renaming ZFS resources. If the dataset is in use by services such
        as SMB, iSCSI, snapshot tasks, replication, or cloud sync, renaming may cause disruptions or service failures.

        Proceed only if you are certain the ZFS resource is not in use and fully understand the risks.
        Set Force to continue.
        """
        if not options['force']:
            raise ValidationError(
                'pool.snapshot.rename.force',
                'No safety checks are performed when renaming ZFS resources; this may break existing usages. '
                'If you understand the risks, please set force and proceed.'
            )
        elif options['new_name'].split('@')[0] != id_.split('@')[0]:
            raise ValidationError(
                'pool.snapshot.rename.new_name',
                'Old and new snapshot must be part of the same ZFS dataset'
            )
        await self.middleware.call(
            'zfs.resource.rename',
            RenameArgs(
                current_name=id_,
                new_name=options['new_name'],
                recursive=options['recursive'],
            )
        )
