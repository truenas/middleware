import errno

from middlewared.api import api_method
from middlewared.api.current import (
    PoolSnapshotEntry,
    PoolSnapshotCloneArgs,
    PoolSnapshotCloneResult,
    PoolSnapshotCreateArgs,
    PoolSnapshotCreateResult,
    PoolSnapshotDeleteArgs,
    PoolSnapshotDeleteResult,
    PoolSnapshotHoldArgs,
    PoolSnapshotHoldResult,
    PoolSnapshotReleaseArgs,
    PoolSnapshotReleaseResult,
    PoolSnapshotRollbackArgs,
    PoolSnapshotRollbackResult,
    PoolSnapshotUpdateArgs,
    PoolSnapshotUpdateResult,
    PoolSnapshotRenameArgs,
    PoolSnapshotRenameResult,
)
from middlewared.service import CRUDService, filterable_api_method, InstanceNotFound, ValidationError
from middlewared.plugins.zfs.destroy_impl import DestroyArgs
from middlewared.plugins.zfs.mount_unmount_impl import MountArgs
from middlewared.plugins.zfs.rename_promote_clone_impl import RenameArgs
from middlewared.utils.filter_list import filter_list


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
            'zfs.resource.snapshot.clone',
            {
                'snapshot': data['snapshot'],
                'dataset': data['dataset_dst'],
                'properties': data['dataset_properties'],
            }
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

    def _transform_snapshot_entry(self, snap):
        """Transform zfs.resource.snapshot.query result to PoolSnapshotEntry format."""
        # Transform properties from new format to old format
        # New: {prop: {raw, source, value}}
        # Old: {prop: {value, rawvalue, source, parsed}}
        old_props = {}
        if snap.get('properties'):
            for prop_name, prop_data in snap['properties'].items():
                if prop_data is None:
                    continue
                # Map source None -> "NONE"
                source = prop_data.get('source')
                if source is None:
                    source = 'NONE'
                old_props[prop_name] = {
                    'value': str(prop_data.get('value', '')),
                    'rawvalue': prop_data.get('raw', ''),
                    'source': source,
                    'parsed': prop_data.get('value'),
                }

        if snap['holds'] and 'truenas' in snap['holds']:
            hold = {'truenas': 1}
        else:
            hold = {}

        return {
            'id': snap['name'],  # id is same as name for snapshots
            'name': snap['name'],
            'pool': snap['pool'],
            'type': 'SNAPSHOT',
            'snapshot_name': snap['snapshot_name'],
            'dataset': snap['dataset'],
            'createtxg': str(snap['createtxg']),
            'properties': old_props,
            'holds': hold,
        }

    def _optimize_snap_query_filters(
        self,
        qry_filters: list,
        paths: list,
        remaining_filters: list
    ) -> bool:
        recursive = False
        for f in qry_filters:
            if len(f) == 3 and f[1] in ('=', 'in'):
                if f[0] in ('id', 'name'):
                    # Direct snapshot lookup
                    if f[1] == '=':
                        paths.append(f[2])
                    else:
                        paths.extend(f[2])
                elif f[0] in ('pool', 'dataset'):
                    # Dataset-based lookup (get all snapshots for dataset)
                    if f[1] == '=':
                        paths.append(f[2])
                    else:
                        paths.extend(f[2])
                    # For dataset filters, we need recursive=True to get all snapshots
                    if f[0] == 'pool':
                        recursive = True
                else:
                    remaining_filters.append(f)
            else:
                remaining_filters.append(f)
        return recursive

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
        `query-options.extra.properties` *(list)*
            List of ZFS property names to retrieve.
        """
        filters = filters or []
        options = options or {}
        extra = options.get('extra', {})

        # Build query args for zfs.resource.snapshot.query
        query_args = {
            'min_txg': extra.get('min_txg', 0),
            'max_txg': extra.get('max_txg', 0),
        }
        if 'properties' in extra:
            query_args['properties'] = extra['properties']

        # Extract path-based filters for efficient querying
        # Optimization: if filtering by id/name/pool/dataset, pass as paths
        paths, remaining_filters = [], []
        recursive = self._optimize_snap_query_filters(filters, paths, remaining_filters)
        if paths:
            query_args['paths'] = paths
            query_args['recursive'] = recursive
        else:
            # legacy behavior would query all snapshots recursively
            # when querying this endpoint with no arguments. That's
            # bad design but we're stuck with it for awhile. If there
            # are no paths that were requested, then set recursive
            # to be true.
            query_args['recursive'] = True

        if extra.get("holds", False):
            query_args["get_holds"] = True

        # Query snapshots using the new efficient endpoint
        snapshots = []
        for i in self.middleware.call_sync(
            'zfs.resource.snapshot.query_impl',
            query_args,
        ):
            # Transform to PoolSnapshotEntry format
            snapshots.append(self._transform_snapshot_entry(i))

        # Apply remaining filters and options using filter_list
        select = options.pop('select', None)
        result = filter_list(snapshots, remaining_filters, options)

        # Add retention info if requested
        if extra.get('retention'):
            if isinstance(result, list):
                result = self.middleware.call_sync('zettarepl.annotate_snapshots', result)
            elif isinstance(result, dict):
                result = self.middleware.call_sync('zettarepl.annotate_snapshots', [result])[0]

        # Apply select if specified
        if select:
            if isinstance(result, list):
                result = [{k: v for k, v in item.items() if k in select} for item in result]
            elif isinstance(result, dict):
                result = {k: v for k, v in result.items() if k in select}

        return result

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
        if '@' not in id_:
            raise ValidationError('pool.snapshot.delete', f'Invalid snapshot name: {id_!r}')

        try:
            self.middleware.call_sync(
                'zfs.resource.destroy',
                DestroyArgs(path=id_, recursive=options['recursive'], defer=options['defer'])
            )
        except ValidationError as ve:
            if ve.errno == errno.ENOENT:
                raise InstanceNotFound(ve.errmsg)
            raise

        # TODO: Events won't be sent for child snapshots in recursive delete
        self.middleware.send_event(
            f'{self._config.namespace}.query', 'REMOVED', id=id_, recursive=options['recursive']
        )
        return True

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
