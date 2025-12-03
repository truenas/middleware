import copy
import errno
import libzfs

from middlewared.service import CallError, CRUDService, ValidationErrors
from middlewared.service_exception import InstanceNotFound
from middlewared.utils.filter_list import filter_list, filter_getattrs

from .utils import get_snapshot_count_cached
from .validation_utils import validate_snapshot_name


class ZFSSnapshotService(CRUDService):

    class Config:
        datastore_primary_key_type = 'string'
        namespace = 'zfs.snapshot'
        process_pool = True
        private = True

    def count(self, dataset_names='*', recursive=False):
        kwargs = {
            'user_props': False,
            'props': ['snapshots_changed'],
            'retrieve_children': (dataset_names == '*' or recursive)
        }
        if dataset_names != '*':
            if not isinstance(dataset_names, list):
                raise ValueError("dataset_names must be '*' or a list")

            kwargs['datasets'] = dataset_names

        try:
            with libzfs.ZFS() as zfs:
                datasets = zfs.datasets_serialized(**kwargs)
                return get_snapshot_count_cached(self.middleware, zfs, datasets)

        except libzfs.ZFSException as e:
            raise CallError(str(e))

    def query(self, filters=None, options=None):
        """
        Query all ZFS Snapshots with `query-filters` and `query-options`.

        `query-options.extra.holds` (bool) specifies whether hold tags for snapshots should be retrieved (false by
            default)

        `query-options.extra.min_txg` (int) can be specified to limit snapshot retrieval based on minimum transaction
            group.

        `query-options.extra.max_txg` (int) can be specified to limit snapshot retrieval based on maximum transaction
            group.

        `query-options.extra.retention` (bool) call `zettarepl.annotate_snapshots` on the query result

        `query-options.extra.properties` (dict) passed to `zfs.snapshots_serialized.props`

        """
        # Special case for faster listing of snapshot names (#53149)
        filters = filters or []
        options = options or {}
        filters_attrs = filter_getattrs(filters)
        extra = copy.deepcopy(options.get('extra', {}))
        min_txg = extra.get('min_txg', 0)
        max_txg = extra.get('max_txg', 0)
        if (
            (
                options.get('select') == ['name'] or
                options.get('count')
            ) and filters_attrs.issubset({'name', 'pool', 'dataset'})
        ):
            kwargs = {}
            other_filters = []

            if not filters and options.get('count'):
                snaps = self.count()
                cnt = 0
                for entry in snaps.values():
                    cnt += entry

                return cnt

            for f in filters:
                if len(f) == 3 and f[0] in ['pool', 'dataset'] and f[1] in ['=', 'in']:
                    if f[1] == '=':
                        kwargs['datasets'] = [f[2]]
                    else:
                        kwargs['datasets'] = f[2]

                    if f[0] == 'dataset':
                        kwargs['recursive'] = False
                else:
                    other_filters.append(f)
            filters = other_filters

            with libzfs.ZFS() as zfs:
                snaps = zfs.snapshots_serialized(['name'], min_txg=min_txg, max_txg=max_txg, **kwargs)

            if filters or len(options) > 1:
                return filter_list(snaps, filters, options)

            return snaps

        if extra.get('retention'):
            if 'id' not in filter_getattrs(filters) and not options.get('limit'):
                raise CallError('`id` or `limit` is required if `retention` is requested', errno.EINVAL)

        holds = extra.get('holds', False)
        properties = extra.get('properties')
        with libzfs.ZFS() as zfs:
            # Handle `id` filter to avoid getting all snapshots first
            kwargs = dict(holds=holds, mounted=False, props=properties, min_txg=min_txg, max_txg=max_txg)
            if filters and len(filters) == 1 and len(filters[0]) == 3 and filters[0][0] in (
                    'id', 'name'
            ) and filters[0][1] == '=':
                kwargs['datasets'] = [filters[0][2]]

            snapshots = zfs.snapshots_serialized(**kwargs)

        # FIXME: awful performance with hundreds/thousands of snapshots
        select = options.pop('select', None)
        result = filter_list(snapshots, filters, options)

        if extra.get('retention'):
            if isinstance(result, list):
                result = self.middleware.call_sync('zettarepl.annotate_snapshots', result)
            elif isinstance(result, dict):
                result = self.middleware.call_sync('zettarepl.annotate_snapshots', [result])[0]

        if select:
            if isinstance(result, list):
                result = [{k: v for k, v in item.items() if k in select} for item in result]
            elif isinstance(result, dict):
                result = {k: v for k, v in result.items() if k in select}

        return result

    def create(self, data: dict):
        """
        Take a snapshot from a given dataset.
        """
        dataset = data['dataset']
        recursive = data.get('recursive', False)
        exclude = data.get('exclude', [])
        properties = data.get('properties', {})
        data.setdefault('vmware_sync', False)
        data.setdefault('suspend_vms', False)

        verrors = ValidationErrors()

        name = None
        if 'name' in data and 'naming_schema' in data:
            verrors.add('snapshot_create.naming_schema', 'You can\'t specify name and naming schema at the same time')
        elif 'name' in data:
            name = data['name']
        elif 'naming_schema' in data:
            # We can't do `strftime` here because we are in the process pool and `TZ` environment variable update
            # is not propagated here.
            name = self.middleware.call_sync('replication.new_snapshot_name', data['naming_schema'])
        else:
            verrors.add('snapshot_create.naming_schema', 'You must specify either name or naming schema')

        if exclude:
            if not recursive:
                verrors.add('snapshot_create.exclude', 'This option has no sense for non-recursive snapshots')
            for k in ['vmware_sync', 'properties']:
                if data[k]:
                    verrors.add(f'snapshot_create.{k}', 'This option is not supported when excluding datasets')

        if name and not validate_snapshot_name(f'{dataset}@{name}'):
            verrors.add('snapshot_create.name', 'Invalid snapshot name')

        verrors.check()

        vmware_context = None
        if data['vmware_sync']:
            vmware_context = self.middleware.call_sync('vmware.snapshot_begin', dataset, recursive)

        affected_vms = {}
        if data['suspend_vms']:
            if affected_vms := self.middleware.call_sync('vm.query_snapshot_begin', dataset, recursive):
                self.middleware.call_sync('vm.suspend_vms', list(affected_vms))

        try:
            if not exclude:
                with libzfs.ZFS() as zfs:
                    ds = zfs.get_dataset(dataset)
                    ds.snapshot(f'{dataset}@{name}', recursive=recursive, fsopts=properties)

                    if vmware_context and vmware_context['vmsynced']:
                        ds.properties['freenas:vmsynced'] = libzfs.ZFSUserProperty('Y')
            else:
                self.middleware.call_sync('zettarepl.create_recursive_snapshot_with_exclude', dataset, name, exclude)

            self.logger.info(f"Snapshot taken: {dataset}@{name}")
        except libzfs.ZFSException as err:
            errno_ = errno.EFAULT
            if 'already exists' in str(err):
                errno_ = errno.EEXIST
            self.logger.error(f'Failed to snapshot {dataset}@{name}: {err}')
            raise CallError(f'Failed to snapshot {dataset}@{name}: {err}', errno_)
        else:
            return self.middleware.call_sync('zfs.snapshot.get_instance', f'{dataset}@{name}')
        finally:
            if affected_vms:
                self.middleware.call_sync('vm.resume_suspended_vms', list(affected_vms))
            if vmware_context:
                self.middleware.call_sync('vmware.snapshot_end', vmware_context)

    def update(self, snap_id, data):
        verrors = ValidationErrors()
        props = data['user_properties_update']
        for index, prop in enumerate(props):
            if prop.get('remove') and 'value' in prop:
                verrors.add(
                    f'snapshot_update.user_properties_update.{index}.remove',
                    'Must not be set when value is specified'
                )
        verrors.check()

        try:
            with libzfs.ZFS() as zfs:
                snap = zfs.get_snapshot(snap_id)
                user_props = {
                    prop['key']: {'value': prop['value']} if 'value' in prop else {'source': 'INHERIT'}
                    for prop in props
                }
                self.middleware.call_sync('zfs.dataset.update_zfs_object_props', user_props, snap)
        except libzfs.ZFSException as e:
            raise CallError(str(e))
        else:
            return self.middleware.call_sync('zfs.snapshot.get_instance', snap_id)

    def delete(self, id_, options={}):
        """
        Delete snapshot of name `id`.

        `options.defer` (bool) will defer the deletion of snapshot.

        """
        defer_ = options.get('defer', False)
        recursive_ = options.get('recursive', False)
        verrors = ValidationErrors()

        try:
            with libzfs.ZFS() as zfs:
                snap = zfs.get_snapshot(id_)
                snap.delete(defer=defer_, recursive=recursive_)
        except libzfs.ZFSException as e:
            if e.code == libzfs.Error.NOENT:
                raise InstanceNotFound(str(e))

            if e.args and isinstance(e.args[0], str) and 'snapshot has dependent clones' in e.args[0]:
                with libzfs.ZFS() as zfs:
                    dep = list(zfs.get_snapshot(id_).dependents)
                    if len(dep) and not defer_:
                        verrors.add(
                            'options.defer',
                            f'Please set this attribute as {snap.name!r} snapshot has dependent clones: '
                            f'{", ".join([i.name for i in dep])}'
                        )
                        verrors.check()

            raise CallError(str(e))
        else:
            return True
