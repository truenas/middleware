import copy
import errno
import os
import subprocess

import libzfs

from middlewared.plugins.zfs_.utils import get_snapshot_count_cached
from middlewared.plugins.zfs_.validation_utils import validate_snapshot_name
from middlewared.schema import accepts, returns, Bool, Dict, List, Str
from middlewared.service import CallError, CRUDService, ValidationErrors, filterable, private
from middlewared.utils import filter_list, filter_getattrs
from middlewared.utils.path import is_child
from middlewared.utils.osc import getmntinfo
from middlewared.validators import Match, ReplicationSnapshotNamingSchema


class ZFSDatasetService(CRUDService):

    class Config:
        namespace = 'zfs.dataset'
        private = True
        process_pool = True

    def path_to_dataset(self, path):
        """
        Convert `path` to a ZFS dataset name. This
        performs lookup through mountinfo.

        Anticipated error conditions are that path is not
        on ZFS or if the boot pool underlies the path. In
        addition to this, all the normal exceptions that
        can be raised by a failed call to os.stat() are
        possible.
        """
        boot_pool = self.middleware.call_sync("boot.pool_name")

        st = os.stat(path)
        mntinfo = getmntinfo(st.st_dev)[st.st_dev]
        ds_name = mntinfo['mount_source']
        if mntinfo['fs_type'] != 'zfs':
            raise CallError(f'{path}: path is not a ZFS filesystem')

        if is_child(ds_name, boot_pool):
            raise CallError(f'{path}: path is on boot pool')

        return ds_name

    def child_dataset_names(self, path):
        # return child datasets given a dataset `path`.
        try:
            with libzfs.ZFS() as zfs:
                return [child.name for child in zfs.get_dataset_by_path(path).children]
        except libzfs.ZFSException as e:
            raise CallError(f'Failed retrieving child datsets for {path} with error {e}')

    @accepts(Str('name'), Dict('options', Bool('recursive', default=False)))
    def mount(self, name, options):
        try:
            with libzfs.ZFS() as zfs:
                dataset = zfs.get_dataset(name)
                if options['recursive']:
                    dataset.mount_recursive()
                else:
                    dataset.mount()
        except libzfs.ZFSException as e:
            self.logger.error('Failed to mount dataset', exc_info=True)
            raise CallError(f'Failed to mount dataset: {e}')

    @accepts(Str('name'), Dict('options', Bool('force', default=False)))
    def umount(self, name, options):
        try:
            with libzfs.ZFS() as zfs:
                dataset = zfs.get_dataset(name)
                dataset.umount(force=options['force'])
        except libzfs.ZFSException as e:
            self.logger.error('Failed to umount dataset', exc_info=True)
            raise CallError(f'Failed to umount dataset: {e}')

    @accepts(
        Str('dataset'),
        Dict(
            'options',
            Str('new_name', required=True, empty=False),
            Bool('recursive', default=False)
        )
    )
    def rename(self, name, options):
        try:
            with libzfs.ZFS() as zfs:
                dataset = zfs.get_dataset(name)
                dataset.rename(options['new_name'], recursive=options['recursive'])
        except libzfs.ZFSException as e:
            self.logger.error('Failed to rename dataset', exc_info=True)
            raise CallError(f'Failed to rename dataset: {e}')

    def promote(self, name):
        try:
            with libzfs.ZFS() as zfs:
                dataset = zfs.get_dataset(name)
                dataset.promote()
        except libzfs.ZFSException as e:
            self.logger.error('Failed to promote dataset', exc_info=True)
            raise CallError(f'Failed to promote dataset: {e}')

    def inherit(self, name, prop, recursive=False):
        try:
            with libzfs.ZFS() as zfs:
                dataset = zfs.get_dataset(name)
                zprop = dataset.properties.get(prop)
                if not zprop:
                    raise CallError(f'Property {prop!r} not found.', errno.ENOENT)
                zprop.inherit(recursive=recursive)
        except libzfs.ZFSException as e:
            if prop != 'mountpoint':
                raise CallError(str(e))

            err = e.code.name
            if err not in ("SHARENFSFAILED", "SHARESMBFAILED"):
                raise CallError(str(e))

            # We set /etc/exports.d to be immutable, which
            # results on inherit of mountpoint failing with
            # SHARENFSFAILED. We give special return in this case
            # so that caller can set this property to "off"
            raise CallError(err, errno.EPROTONOSUPPORT)

    def destroy_snapshots(self, name, snapshot_spec):
        try:
            with libzfs.ZFS() as zfs:
                dataset = zfs.get_dataset(name)
                return dataset.delete_snapshots(snapshot_spec)
        except libzfs.ZFSException as e:
            raise CallError(str(e))


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

    @accepts(Dict(
        'snapshot_create',
        Str('dataset', required=True, empty=False),
        Str('name', empty=False),
        Str('naming_schema', empty=False, validators=[ReplicationSnapshotNamingSchema()]),
        Bool('recursive', default=False),
        List('exclude', items=[Str('dataset')]),
        Bool('suspend_vms', default=False),
        Bool('vmware_sync', default=False),
        Dict('properties', additional_attrs=True),
    ))
    def do_create(self, data):
        """
        Take a snapshot from a given dataset.
        """

        dataset = data['dataset']
        recursive = data['recursive']
        exclude = data['exclude']
        properties = data['properties']

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

        if verrors:
            raise verrors

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
            self.logger.error(f'Failed to snapshot {dataset}@{name}: {err}')
            raise CallError(f'Failed to snapshot {dataset}@{name}: {err}')
        else:
            return self.middleware.call_sync('zfs.snapshot.get_instance', f'{dataset}@{name}')
        finally:
            if affected_vms:
                self.middleware.call_sync('vm.resume_suspended_vms', list(affected_vms))
            if vmware_context:
                self.middleware.call_sync('vmware.snapshot_end', vmware_context)

    @accepts(
        Str('id'), Dict(
            'snapshot_update',
            List(
                'user_properties_update',
                items=[Dict(
                    'user_property',
                    Str('key', required=True, validators=[Match(r'.*:.*')]),
                    Str('value'),
                    Bool('remove'),
                )],
            ),
        )
    )
    def do_update(self, snap_id, data):
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
                user_props = self.middleware.call_sync('pool.dataset.get_create_update_user_props', props, True)
                self.middleware.call_sync('zfs.dataset.update_zfs_object_props', user_props, snap)
        except libzfs.ZFSException as e:
            raise CallError(str(e))
        else:
            return self.middleware.call_sync('zfs.snapshot.get_instance', snap_id)

    @accepts(Dict(
        'snapshot_remove',
        Str('dataset', required=True),
        Str('name', required=True),
        Bool('defer_delete')
    ))
    def remove(self, data):
        """
        Remove a snapshot from a given dataset.

        Returns:
            bool: True if succeed otherwise False.
        """
        self.logger.debug('zfs.snapshot.remove is deprecated, use zfs.snapshot.delete')
        snapshot_name = data['dataset'] + '@' + data['name']
        try:
            self.do_delete(snapshot_name, {'defer': data.get('defer_delete') or False})
        except Exception:
            return False
        return True

    @accepts(
        Str('id'),
        Dict(
            'options',
            Bool('defer', default=False),
            Bool('recursive', default=False),
        ),
    )
    def do_delete(self, id, options):
        """
        Delete snapshot of name `id`.

        `options.defer` will defer the deletion of snapshot.
        """
        try:
            with libzfs.ZFS() as zfs:
                snap = zfs.get_snapshot(id)
                snap.delete(defer=options['defer'], recursive=options['recursive'])
        except libzfs.ZFSException as e:
            raise CallError(str(e))
        else:
            return True

    @accepts(Dict(
        'snapshot_clone',
        Str('snapshot', required=True, empty=False),
        Str('dataset_dst', required=True, empty=False),
        Dict(
            'dataset_properties',
            additional_attrs=True,
        )
    ))
    def clone(self, data):
        """
        Clone a given snapshot to a new dataset.

        Returns:
            bool: True if succeed otherwise False.
        """

        snapshot = data.get('snapshot', '')
        dataset_dst = data.get('dataset_dst', '')
        props = data['dataset_properties']

        try:
            with libzfs.ZFS() as zfs:
                snp = zfs.get_snapshot(snapshot)
                snp.clone(dataset_dst, props)
                dataset = zfs.get_dataset(dataset_dst)
                if dataset.type.name == 'FILESYSTEM':
                    dataset.mount_recursive()
            self.logger.info("Cloned snapshot {0} to dataset {1}".format(snapshot, dataset_dst))
            return True
        except libzfs.ZFSException as err:
            self.logger.error("{0}".format(err))
            raise CallError(f'Failed to clone snapshot: {err}')

    @accepts(
        Str('id'),
        Dict(
            'options',
            Bool('recursive', default=False),
            Bool('recursive_clones', default=False),
            Bool('force', default=False),
            Bool('recursive_rollback', default=False),
        ),
    )
    def rollback(self, id, options):
        """
        Rollback to a given snapshot `id`.

        `options.recursive` will destroy any snapshots and bookmarks more recent than the one
        specified.

        `options.recursive_clones` is just like `recursive` but will also destroy any clones.

        `options.force` will force unmount of any clones.

        `options.recursive_rollback` will do a complete recursive rollback of each child snapshots for `id`. If
        any child does not have specified snapshot, this operation will fail.
        """
        args = []
        if options['force']:
            args += ['-f']
        if options['recursive']:
            args += ['-r']
        if options['recursive_clones']:
            args += ['-R']

        if options['recursive_rollback']:
            dataset, snap_name = id.rsplit('@', 1)
            datasets = set({
                f'{ds["id"]}@{snap_name}' for ds in self.middleware.call_sync(
                    'zfs.dataset.query', [['OR', [['id', '^', f'{dataset}/'], ['id', '=', dataset]]]]
                )
            })

            for snap in filter(lambda sn: self.middleware.call_sync('zfs.snapshot.query', [['id', '=', sn]]), datasets):
                self.rollback_impl(args, snap)

        else:
            self.rollback_impl(args, id)

    @private
    def rollback_impl(self, args, id):
        try:
            subprocess.run(
                ['zfs', 'rollback'] + args + [id], text=True, capture_output=True, check=True,
            )
        except subprocess.CalledProcessError as e:
            raise CallError(f'Failed to rollback snapshot: {e.stderr.strip()}')

    @accepts(
        Str('id'),
        Dict(
            'options',
            Bool('recursive', default=False),
        ),
    )
    @returns()
    def hold(self, id, options):
        """
        Holds snapshot `id`.

        `truenas` tag will be added to the snapshot's tag namespace.

        `options.recursive` will hold snapshots recursively.
        """
        try:
            with libzfs.ZFS() as zfs:
                snapshot = zfs.get_snapshot(id)
                snapshot.hold('truenas', options['recursive'])
        except libzfs.ZFSException as err:
            raise CallError(f'Failed to hold snapshot: {err}')

    @accepts(
        Str('id'),
        Dict(
            'options',
            Bool('recursive', default=False),
        ),
    )
    @returns()
    def release(self, id, options):
        """
        Release held snapshot `id`.

        Will remove all hold tags from the specified snapshot.

        `options.recursive` will release snapshots recursively. Please note that only the tags that are present on the
        parent snapshot will be removed.
        """
        try:
            with libzfs.ZFS() as zfs:
                snapshot = zfs.get_snapshot(id)
                for tag in snapshot.holds:
                    snapshot.release(tag, options['recursive'])
        except libzfs.ZFSException as err:
            raise CallError(f'Failed to release snapshot: {err}')
