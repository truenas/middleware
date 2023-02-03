import copy
import libzfs

from middlewared.service import CallError, CRUDService, filterable, private
from middlewared.utils import filter_list, filter_getattrs

from .utils import get_snapshot_count_cached


class ZFSSnapshot(CRUDService):

    class Config:
        datastore_primary_key_type = 'string'
        namespace = 'zfs.snapshot'
        process_pool = True
        cli_namespace = 'storage.snapshot'

    @private
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

        prefetch = True
        if dataset_names != '*' and len(dataset_names) == 1 and not recursive:
            prefetch = False

        try:
            with libzfs.ZFS() as zfs:
                datasets = zfs.datasets_serialized(**kwargs)
                return get_snapshot_count_cached(self.middleware, zfs, datasets, prefetch)

        except libzfs.ZFSException as e:
            raise CallError(str(e))

    @filterable
    def query(self, filters, options):
        """
        Query all ZFS Snapshots with `query-filters` and `query-options`.

        `query-options.extra.holds` specifies whether hold tags for snapshots should be retrieved (false by default)

        `query-options.extra.min_txg` can be specified to limit snapshot retrieval based on minimum transaction group.

        `query-options.extra.max_txg` can be specified to limit snapshot retrieval based on maximum transaction group.
        """
        # Special case for faster listing of snapshot names (#53149)
        filters_attrs = filter_getattrs(filters)
        extra = copy.deepcopy(options['extra'])
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

        if options['extra'].get('retention'):
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

        if options['extra'].get('retention'):
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
