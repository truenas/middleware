import copy
import errno
import os
import subprocess
from collections import defaultdict
from copy import deepcopy

import libzfs

from middlewared.plugins.zfs_.utils import zvol_path_to_name, unlocked_zvols_fast
from middlewared.plugins.zfs_.validation_utils import validate_snapshot_name
from middlewared.schema import accepts, Any, Bool, Dict, Int, List, Ref, Str
from middlewared.service import (
    CallError, CRUDService, ValidationErrors, filterable, job, private,
)
from middlewared.utils import filter_list, filter_getattrs
from middlewared.utils.path import is_child
from middlewared.utils.osc import getmntinfo
from middlewared.validators import Match, ReplicationSnapshotNamingSchema


SEARCH_PATHS = ['/dev/disk/by-partuuid', '/dev']


class ZFSSetPropertyError(CallError):
    def __init__(self, property, error):
        self.property = property
        self.error = error
        super().__init__(f'Failed to update dataset: failed to set property {self.property}: {self.error}')


def convert_topology(zfs, vdevs):
    topology = defaultdict(list)
    for vdev in vdevs:
        children = []
        for device in vdev['devices']:
            z_cvdev = libzfs.ZFSVdev(zfs, 'disk')
            z_cvdev.type = 'disk'
            z_cvdev.path = device
            children.append(z_cvdev)

        if vdev['type'] == 'STRIPE':
            topology[vdev['root'].lower()].extend(children)
        else:
            z_vdev = libzfs.ZFSVdev(zfs, 'disk')
            z_vdev.type = vdev['type'].lower()
            z_vdev.children = children
            topology[vdev['root'].lower()].append(z_vdev)
    return topology


def find_vdev(pool, vname):
    """
    Find a vdev in the given `pool` using `vname` looking for
    guid or path

    Returns:
        libzfs.ZFSVdev object
    """
    children = []
    for vdevs in pool.groups.values():
        children += vdevs
    while children:
        child = children.pop()

        if str(vname) == str(child.guid):
            return child

        if child.type == 'disk':
            path = child.path.replace('/dev/', '')
            if path == vname:
                return child

        children += list(child.children)


class ZFSPoolService(CRUDService):

    class Config:
        namespace = 'zfs.pool'
        private = True
        process_pool = True

    @filterable
    def query(self, filters, options):
        # We should not get datasets, there is zfs.dataset.query for that
        state_kwargs = {'datasets_recursive': False}
        with libzfs.ZFS() as zfs:
            # Handle `id` filter specially to avoiding getting all pool
            if filters and len(filters) == 1 and list(filters[0][:2]) == ['id', '=']:
                try:
                    pools = [zfs.get(filters[0][2]).__getstate__(**state_kwargs)]
                except libzfs.ZFSException:
                    pools = []
            else:
                pools = [i.__getstate__(**state_kwargs) for i in zfs.pools]
        return filter_list(pools, filters, options)

    def query_imported_fast(self, name_filters=None):
        # the equivalent of running `zpool list -H -o guid,name` from cli
        # name_filters will be a list of pool names
        out = {}
        name_filters = name_filters or []
        with os.scandir('/proc/spl/kstat/zfs') as it:
            for entry in filter(lambda entry: not name_filters or entry.name in name_filters, it):
                if not entry.is_dir() or entry.name == '$import':
                    continue

                guid = self.guid_fast(entry.name)
                state = self.state_fast(entry.name)
                out.update({guid: {'name': entry.name, 'state': state}})

        return out

    def is_upgraded(self, pool_name):
        enabled = (libzfs.FeatureState.ENABLED, libzfs.FeatureState.ACTIVE)
        with libzfs.ZFS() as zfs:
            try:
                pool = zfs.get(pool_name)
            except libzfs.ZFSException:
                raise CallError(f'{pool_name!r} not found', errno.ENOENT)

            return all((i.state in enabled for i in pool.features))

    @accepts(
        Dict(
            'zfspool_create',
            Str('name', required=True),
            List('vdevs', items=[
                Dict(
                    'vdev',
                    Str('root', enum=['DATA', 'CACHE', 'LOG', 'SPARE', 'SPECIAL', 'DEDUP'], required=True),
                    Str('type', enum=['RAIDZ1', 'RAIDZ2', 'RAIDZ3', 'MIRROR', 'STRIPE'], required=True),
                    List('devices', items=[Str('disk')], required=True),
                ),
            ], required=True),
            Dict('options', additional_attrs=True),
            Dict('fsoptions', additional_attrs=True),
        ),
    )
    def do_create(self, data):
        with libzfs.ZFS() as zfs:
            topology = convert_topology(zfs, data['vdevs'])
            zfs.create(data['name'], topology, data['options'], data['fsoptions'])

        return self.middleware.call_sync('zfs.pool.get_instance', data['name'])

    @accepts(Str('pool'), Dict(
        'options',
        Dict('properties', additional_attrs=True),
    ))
    def do_update(self, name, options):
        try:
            with libzfs.ZFS() as zfs:
                pool = zfs.get(name)
                for k, v in options['properties'].items():
                    prop = pool.properties[k]
                    if 'value' in v:
                        prop.value = v['value']
                    elif 'parsed' in v:
                        prop.parsed = v['parsed']
        except libzfs.ZFSException as e:
            raise CallError(str(e))
        else:
            return options

    @accepts(Str('pool'), Dict(
        'options',
        Bool('force', default=False),
    ))
    def do_delete(self, name, options):
        try:
            with libzfs.ZFS() as zfs:
                zfs.destroy(name, force=options['force'])
        except libzfs.ZFSException as e:
            errno_ = errno.EFAULT
            if e.code == libzfs.Error.UMOUNTFAILED:
                errno_ = errno.EBUSY
            raise CallError(str(e), errno_)
        else:
            return True

    @accepts(Str('pool', required=True))
    def upgrade(self, pool):
        try:
            with libzfs.ZFS() as zfs:
                zfs.get(pool).upgrade()
        except libzfs.ZFSException as e:
            raise CallError(str(e))

    @accepts(Str('pool'), Dict(
        'options',
        Bool('force', default=False),
    ))
    def export(self, name, options):
        try:
            with libzfs.ZFS() as zfs:
                # FIXME: force not yet implemented
                pool = zfs.get(name)
                zfs.export_pool(pool)
        except libzfs.ZFSException as e:
            raise CallError(str(e))

    @accepts(Str('pool'))
    def get_devices(self, name):
        try:
            with libzfs.ZFS() as zfs:
                return [i.replace('/dev/', '') for i in zfs.get(name).disks]
        except libzfs.ZFSException as e:
            raise CallError(str(e), errno.ENOENT)

    @accepts(
        Str('name'),
        List('new', default=None, null=True),
        List('existing', items=[
            Dict(
                'attachvdev',
                Str('target'),
                Str('type', enum=['DISK']),
                Str('path'),
            ),
        ], null=True, default=None),
    )
    @job()
    def extend(self, job, name, new, existing):
        """
        Extend a zfs pool `name` with `new` vdevs or attach to `existing` vdevs.
        """

        if new is None and existing is None:
            raise CallError('New or existing vdevs must be provided', errno.EINVAL)

        try:
            with libzfs.ZFS() as zfs:
                pool = zfs.get(name)

                if new:
                    topology = convert_topology(zfs, new)
                    pool.attach_vdevs(topology)

                # Make sure we can find all target vdev
                for i in (existing or []):
                    target = find_vdev(pool, i['target'])
                    if target is None:
                        raise CallError(f"Failed to find vdev for {i['target']}", errno.EINVAL)
                    i['target'] = target

                for i in (existing or []):
                    newvdev = libzfs.ZFSVdev(zfs, i['type'].lower())
                    newvdev.path = i['path']
                    i['target'].attach(newvdev)

        except libzfs.ZFSException as e:
            raise CallError(str(e), e.code)

    def __zfs_vdev_operation(self, name, label, op, *args):
        try:
            with libzfs.ZFS() as zfs:
                pool = zfs.get(name)
                target = find_vdev(pool, label)
                if target is None:
                    raise CallError(f'Failed to find vdev for {label}', errno.EINVAL)
                op(target, *args)
        except libzfs.ZFSException as e:
            raise CallError(str(e), e.code)

    @accepts(Str('pool'), Str('label'), Dict('options', Bool('clear_label', default=False)))
    def detach(self, name, label, options):
        """
        Detach device `label` from the pool `pool`.
        """
        self.detach_remove_impl('detach', name, label, options)

    def detach_remove_impl(self, op, name, label, options):
        def impl(target):
            getattr(target, op)()
            if options['clear_label']:
                self.clear_label(target.path)
        self.__zfs_vdev_operation(name, label, impl)

    @accepts(Str('pool'))
    def guid_fast(self, pool):
        """
        Lockless read of zpool guid. Raises FileNotFoundError
        if pool not imported.
        """
        with open(f'/proc/spl/kstat/zfs/{pool}/guid') as f:
            guid_out = f.read()

        return guid_out.strip()

    @accepts(Str('pool'))
    def state_fast(self, pool):
        """
        Lockless read of zpool state. Raises FileNotFoundError
        if pool not imported.
        """
        with open(f'/proc/spl/kstat/zfs/{pool}/state') as f:
            state = f.read()

        return state.strip()

    @accepts(Str('device'))
    def clear_label(self, device):
        """
        Clear label from `device`.
        """
        try:
            libzfs.clear_label(device)
        except (libzfs.ZFSException, OSError) as e:
            raise CallError(str(e))

    @accepts(Str('pool'), Str('label'))
    def offline(self, name, label):
        """
        Offline device `label` from the pool `pool`.
        """
        self.__zfs_vdev_operation(name, label, lambda target: target.offline())

    @accepts(
        Str('pool'), Str('label'), Bool('expand', default=False)
    )
    def online(self, name, label, expand):
        """
        Online device `label` from the pool `pool`.
        """
        self.__zfs_vdev_operation(name, label, lambda target, *args: target.online(*args), expand)

    @accepts(Str('pool'), Str('label'), Dict('options', Bool('clear_label', default=False)))
    def remove(self, name, label, options):
        """
        Remove device `label` from the pool `pool`.
        """
        self.detach_remove_impl('remove', name, label, options)

    @accepts(Str('pool'), Str('label'), Str('dev'))
    def replace(self, name, label, dev):
        """
        Replace device `label` with `dev` in pool `name`.
        """
        try:
            with libzfs.ZFS() as zfs:
                pool = zfs.get(name)
                target = find_vdev(pool, label)
                if target is None:
                    raise CallError(f'Failed to find vdev for {label}', errno.EINVAL)

                newvdev = libzfs.ZFSVdev(zfs, 'disk')
                newvdev.path = f'/dev/{dev}'
                # FIXME: Replace using old path is not working for some reason
                # Lets use guid for now.
                target.path = str(target.guid)
                target.replace(newvdev)
        except libzfs.ZFSException as e:
            raise CallError(str(e), e.code)

    @accepts(
        Str('name', required=True),
        Str('action', enum=['START', 'STOP', 'PAUSE'], default='START')
    )
    def scrub_action(self, name, action):
        """
        Start/Stop/Pause a scrub on pool `name`.
        """
        if action != 'PAUSE':
            try:
                with libzfs.ZFS() as zfs:
                    pool = zfs.get(name)

                    if action == 'START':
                        pool.start_scrub()
                    else:
                        pool.stop_scrub()
            except libzfs.ZFSException as e:
                raise CallError(str(e), e.code)
        else:
            proc = subprocess.Popen(
                f'zpool scrub -p {name}'.split(' '),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            proc.communicate()

            if proc.returncode != 0:
                raise CallError('Unable to pause scrubbing')

    def scrub_state(self, name):
        with libzfs.ZFS() as zfs:
            return zfs.get(name).scrub.__getstate__()

    @accepts()
    def find_import(self):
        with libzfs.ZFS() as zfs:
            return [i.__getstate__() for i in zfs.find_import(search_paths=SEARCH_PATHS)]

    @accepts(
        Str('name_or_guid'),
        Dict('properties', additional_attrs=True),
        Bool('any_host', default=True),
        Str('cachefile', null=True, default=None),
        Str('new_name', null=True, default=None),
        Dict(
            'import_options',
            Bool('missing_log', default=False),
        ),
    )
    def import_pool(self, name_or_guid, properties, any_host, cachefile, new_name, import_options):
        with libzfs.ZFS() as zfs:
            for pool in zfs.find_import(cachefile=cachefile, search_paths=SEARCH_PATHS):
                if pool.name == name_or_guid or str(pool.guid) == name_or_guid:
                    found = pool
                    break
            else:
                raise CallError(f'Pool {name_or_guid} not found.', errno.ENOENT)

            missing_log = import_options['missing_log']
            pool_name = new_name or found.name
            try:
                zfs.import_pool(found, pool_name, properties, missing_log=missing_log, any_host=any_host)
            except libzfs.ZFSException as e:
                # We only log if some datasets failed to mount after pool import
                if e.code != libzfs.Error.MOUNTFAILED:
                    raise CallError(f'Failed to import {pool_name!r} pool: {e}', e.code)
                else:
                    self.logger.error(
                        'Failed to mount datasets after importing "%s" pool: %s', name_or_guid, str(e), exc_info=True
                    )

    @accepts(Str('pool'))
    def find_not_online(self, pool):
        pool = self.middleware.call_sync('zfs.pool.query', [['id', '=', pool]], {'get': True})

        unavails = []
        for nodes in pool['groups'].values():
            for node in nodes:
                unavails.extend(self.__find_not_online(node))
        return unavails

    def __find_not_online(self, node):
        if len(node['children']) == 0 and node['status'] not in ('ONLINE', 'AVAIL'):
            return [node]

        unavails = []
        for child in node['children']:
            unavails.extend(self.__find_not_online(child))
        return unavails

    def get_vdev(self, name, vname):
        try:
            with libzfs.ZFS() as zfs:
                pool = zfs.get(name)
                vdev = find_vdev(pool, vname)
                if not vdev:
                    raise CallError(f'{vname} not found in {name}', errno.ENOENT)
                return vdev.__getstate__()
        except libzfs.ZFSException as e:
            raise CallError(str(e))


class ZFSDatasetService(CRUDService):

    class Config:
        namespace = 'zfs.dataset'
        private = True
        process_pool = True

    def locked_datasets(self, names=None):
        query_filters = []
        if names is not None:
            names_optimized = []
            for name in sorted(names, key=len):
                if not any(name.startswith(f'{existing_name}/') for existing_name in names_optimized):
                    names_optimized.append(name)

            query_filters.append(['id', 'in', names_optimized])

        result = self.flatten_datasets(self.query(query_filters, {
            'extra': {
                'flat': False,  # So child datasets are also queried
                'properties': ['encryption', 'keystatus', 'mountpoint']
            },
        }))

        post_filters = [['encrypted', '=', True]]

        try:
            about_to_lock_dataset = self.middleware.call_sync('cache.get', 'about_to_lock_dataset')
        except KeyError:
            about_to_lock_dataset = None

        post_filters.append([
            'OR', [['key_loaded', '=', False]] + (
                [['id', '=', about_to_lock_dataset], ['id', '^', f'{about_to_lock_dataset}/']]
                if about_to_lock_dataset else []
            )
        ])

        return [
            {
                'id': dataset['id'],
                'mountpoint': dataset['properties'].get('mountpoint', {}).get('value'),
            }
            for dataset in filter_list(result, post_filters)
        ]

    def flatten_datasets(self, datasets):
        return sum([[deepcopy(ds)] + self.flatten_datasets(ds.get('children') or []) for ds in datasets], [])

    @filterable
    def query(self, filters, options):
        """
        In `query-options` we can provide `extra` arguments which control which data should be retrieved
        for a dataset.

        `query-options.extra.snapshots` is a boolean which when set will retrieve snapshots for the dataset in question
        by adding a snapshots key to the dataset data.

        `query-options.extra.retrieve_children` is a boolean set to true by default. When set to true, will retrieve
        all children datasets which can cause a performance penalty. When set to false, will not retrieve children
        datasets which does not incur the performance penalty.

        `query-options.extra.properties` is a list of properties which should be retrieved. If null ( by default ),
        it would retrieve all properties, if empty, it will retrieve no property.

        We provide 2 ways how zfs.dataset.query returns dataset's data. First is a flat structure ( default ), which
        means that all the datasets in the system are returned as separate objects which also contain all the data
        their is for their children. This retrieval type is slightly slower because of duplicates which exist in
        each object.
        Second type is hierarchical where only top level datasets are returned in the list and they contain all the
        children there are for them in `children` key. This retrieval type is slightly faster.
        These options are controlled by `query-options.extra.flat` attribute which defaults to true.

        `query-options.extra.user_properties` controls if user defined properties of datasets should be retrieved
        or not.

        While we provide a way to exclude all properties from data retrieval, we introduce a single attribute
        `query-options.extra.retrieve_properties` which if set to false will make sure that no property is retrieved
        whatsoever and overrides any other property retrieval attribute.
        """
        options = options or {}
        extra = options.get('extra', {}).copy()
        props = extra.get('properties', None)
        flat = extra.get('flat', True)
        user_properties = extra.get('user_properties', True)
        retrieve_properties = extra.get('retrieve_properties', True)
        retrieve_children = extra.get('retrieve_children', True)
        snapshots = extra.get('snapshots')
        snapshots_recursive = extra.get('snapshots_recursive')
        snapshots_properties = extra.get('snapshots_properties', [])
        if not retrieve_properties:
            # This is a short hand version where consumer can specify that they don't want any property to
            # be retrieved
            user_properties = False
            props = []

        with libzfs.ZFS() as zfs:
            # Handle `id` filter specially to avoiding getting all datasets
            kwargs = dict(
                props=props, user_props=user_properties, snapshots=snapshots, retrieve_children=retrieve_children,
                snapshots_recursive=snapshots_recursive, snapshot_props=snapshots_properties
            )
            if filters and filters[0][0] == 'id':
                if filters[0][1] == '=':
                    kwargs['datasets'] = [filters[0][2]]
                if filters[0][1] == 'in':
                    kwargs['datasets'] = filters[0][2]

            datasets = zfs.datasets_serialized(**kwargs)
            if flat:
                datasets = self.flatten_datasets(datasets)
            else:
                datasets = list(datasets)

        return filter_list(datasets, filters, options)

    def query_for_quota_alert(self):
        options = {
            'extra': {
                'properties': [
                    'name',
                    'quota',
                    'available',
                    'refquota',
                    'used',
                    'usedbydataset',
                    'mounted',
                    'mountpoint',
                    'org.freenas:quota_warning',
                    'org.freenas:quota_critical',
                    'org.freenas:refquota_warning',
                    'org.freenas:refquota_critial',
                ]
            }
        }
        return [
            {k: v for k, v in i['properties'].items() if k in options['extra']['properties']}
            for i in self.query([], options)
        ]

    @accepts(
        Ref('query-filters'),
        Ref('query-options'),
        List(
            'additional_information',
            items=[Str('desideratum', enum=['SIZE', 'RO', 'DEVID', 'ATTACHMENT'])]
        )
    )
    def unlocked_zvols_fast(self, filters, options, additional_information):
        """
        Fast check for zvol information. Supports `additional_information` to
        expand output on an as-needed basis. Adding additional_information to
        the output may impact performance of 'fast' method.
        """
        def get_attachments():
            extents = self.middleware.call_sync('iscsi.extent.query', [('type', '=', 'DISK')])
            iscsi_zvols = {
                zvol_path_to_name('/dev/' + i['path']): i for i in extents
            }

            vm_devices = self.middleware.call_sync('vm.device.query', [['dtype', '=', 'DISK']])
            vm_zvols = {
                zvol_path_to_name(i['attributes']['path']): i for i in vm_devices
            }
            return {
                'iscsi.extent.query': iscsi_zvols,
                'vm.devices.query': vm_zvols
            }

        data = {}
        if 'ATTACHMENT' in additional_information:
            data['attachments'] = get_attachments()

        zvol_list = list(unlocked_zvols_fast(additional_information, data).values())
        return filter_list(zvol_list, filters, options)

    def common_load_dataset_checks(self, ds):
        self.common_encryption_checks(ds)
        if ds.key_loaded:
            raise CallError(f'{id} key is already loaded')

    def common_encryption_checks(self, ds):
        if not ds.encrypted:
            raise CallError(f'{id} is not encrypted')

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

    def get_quota(self, ds, quota_type):
        if quota_type == 'dataset':
            dataset = self.query([('id', '=', ds)], {'get': True})
            return [{
                'quota_type': 'DATASET',
                'id': ds,
                'name': ds,
                'quota': int(dataset['properties']['quota']['rawvalue']),
                'refquota': int(dataset['properties']['refquota']['rawvalue']),
                'used_bytes': int(dataset['properties']['used']['rawvalue']),
            }]

        quota_list = []
        quota_get = subprocess.run(
            ['zfs', f'{quota_type}space', '-H', '-n', '-p', '-o', 'name,used,quota,objquota,objused', ds],
            capture_output=True,
            check=False,
        )
        if quota_get.returncode != 0:
            raise CallError(
                f'Failed to get {quota_type} quota for {ds}: [{quota_get.stderr.decode()}]'
            )

        for quota in quota_get.stdout.decode().splitlines():
            m = quota.split('\t')
            if len(m) != 5:
                self.logger.debug('Invalid %s quota: %s',
                                  quota_type.lower(), quota)
                continue

            entry = {
                'quota_type': quota_type.upper(),
                'id': int(m[0]),
                'name': None,
                'quota': int(m[2]) if m[2] != '-' else 0,
                'used_bytes': int(m[1]) if m[1] != '-' else 0,
                'used_percent': 0,
                'obj_quota': int(m[3]) if m[3] != '-' else 0,
                'obj_used': int(m[4]) if m[4] != '-' else 0,
                'obj_used_percent': 0,
            }
            if entry['quota'] > 0:
                entry['used_percent'] = entry['used_bytes'] / entry['quota'] * 100

            if entry['obj_quota'] > 0:
                entry['obj_used_percent'] = entry['obj_used'] / entry['obj_quota'] * 100

            try:
                if entry['quota_type'] == 'USER':
                    entry['name'] = (
                        self.middleware.call_sync('user.get_user_obj',
                                                  {'uid': entry['id']})
                    )['pw_name']
                else:
                    entry['name'] = (
                        self.middleware.call_sync('group.get_group_obj',
                                                  {'gid': entry['id']})
                    )['gr_name']

            except Exception:
                self.logger.debug('Unable to resolve %s id %d to name',
                                  quota_type.lower(), entry['id'])
                pass

            quota_list.append(entry)

        return quota_list

    def set_quota(self, ds, quota_list):
        cmd = ['zfs', 'set']
        cmd.extend(quota_list)
        cmd.append(ds)
        quota_set = subprocess.run(cmd, check=False)
        if quota_set.returncode != 0:
            raise CallError(f'Failed to set userspace quota on {ds}: [{quota_set.stderr.decode()}]')

    @accepts(
        Str('id'),
        Dict(
            'load_key_options',
            Bool('mount', default=True),
            Bool('recursive', default=False),
            Any('key', default=None, null=True),
            Str('key_location', default=None, null=True),
        ),
    )
    def load_key(self, id, options):
        mount_ds = options.pop('mount')
        recursive = options.pop('recursive')
        try:
            with libzfs.ZFS() as zfs:
                ds = zfs.get_dataset(id)
                self.common_load_dataset_checks(ds)
                ds.load_key(**options)
        except libzfs.ZFSException as e:
            self.logger.error(f'Failed to load key for {id}', exc_info=True)
            raise CallError(f'Failed to load key for {id}: {e}')
        else:
            if mount_ds:
                self.mount(id, {'recursive': recursive})

    @accepts(Str('name'), List('params', private=True))
    @job()
    def bulk_process(self, job, name, params):
        f = getattr(self, name, None)
        if not f:
            raise CallError(f'{name} method not found in zfs.dataset')

        statuses = []
        for i in params:
            result = error = None
            try:
                result = f(*i)
            except Exception as e:
                error = str(e)
            finally:
                statuses.append({'result': result, 'error': error})

        return statuses

    @accepts(
        Str('id'),
        Dict(
            'check_key',
            Any('key', default=None, null=True),
            Str('key_location', default=None, null=True),
        )
    )
    def check_key(self, id, options):
        """
        Returns `true` if the `key` is valid, `false` otherwise.
        """
        try:
            with libzfs.ZFS() as zfs:
                ds = zfs.get_dataset(id)
                self.common_encryption_checks(ds)
                return ds.check_key(**options)
        except libzfs.ZFSException as e:
            self.logger.error(f'Failed to check key for {id}', exc_info=True)
            raise CallError(f'Failed to check key for {id}: {e}')

    @accepts(
        Str('id'),
        Dict(
            'unload_key_options',
            Bool('recursive', default=False),
            Bool('force_umount', default=False),
            Bool('umount', default=False),
        )
    )
    def unload_key(self, id, options):
        force = options.pop('force_umount')
        if options.pop('umount') and self.middleware.call_sync(
            'zfs.dataset.query', [['id', '=', id]], {'extra': {'retrieve_children': False}, 'get': True}
        )['properties'].get('mountpoint', {}).get('value', 'none') != 'none':
            self.umount(id, {'force': force})
        try:
            with libzfs.ZFS() as zfs:
                ds = zfs.get_dataset(id)
                self.common_encryption_checks(ds)
                if not ds.key_loaded:
                    raise CallError(f'{id}\'s key is not loaded')
                ds.unload_key(**options)
        except libzfs.ZFSException as e:
            self.logger.error(f'Failed to unload key for {id}', exc_info=True)
            raise CallError(f'Failed to unload key for {id}: {e}')

    @accepts(
        Str('id'),
        Dict(
            'change_key_options',
            Dict(
                'encryption_properties',
                Str('keyformat'),
                Str('keylocation'),
                Int('pbkdf2iters')
            ),
            Bool('load_key', default=True),
            Any('key', default=None, null=True),
        ),
    )
    def change_key(self, id, options):
        try:
            with libzfs.ZFS() as zfs:
                ds = zfs.get_dataset(id)
                self.common_encryption_checks(ds)
                ds.change_key(props=options['encryption_properties'], load_key=options['load_key'], key=options['key'])
        except libzfs.ZFSException as e:
            self.logger.error(f'Failed to change key for {id}', exc_info=True)
            raise CallError(f'Failed to change key for {id}: {e}')

    @accepts(
        Str('id'),
        Dict(
            'change_encryption_root_options',
            Bool('load_key', default=True),
        )
    )
    def change_encryption_root(self, id, options):
        try:
            with libzfs.ZFS() as zfs:
                ds = zfs.get_dataset(id)
                ds.change_key(load_key=options['load_key'], inherit=True)
        except libzfs.ZFSException as e:
            raise CallError(f'Failed to change encryption root for {id}: {e}')

    @accepts(Dict(
        'dataset_create',
        Bool('create_ancestors', default=False),
        Str('name', required=True),
        Str('type', enum=['FILESYSTEM', 'VOLUME'], default='FILESYSTEM'),
        Dict(
            'properties',
            Bool('sparse'),
            additional_attrs=True,
        ),
    ))
    def do_create(self, data):
        """
        Creates a ZFS dataset.
        """

        verrors = ValidationErrors()

        if '/' not in data['name']:
            verrors.add('name', 'You need a full name, e.g. pool/newdataset')

        if verrors:
            raise verrors

        properties = data.get('properties') or {}
        sparse = properties.pop('sparse', False)
        params = {}

        for k, v in data['properties'].items():
            params[k] = v

        # it's important that we set xattr=sa for various
        # performance reasons related to ea handling
        # pool.dataset.create already sets this by default
        # so mirror the behavior here
        if data['type'] == 'FILESYSTEM' and 'xattr' not in params:
            params['xattr'] = 'sa'

        try:
            with libzfs.ZFS() as zfs:
                pool = zfs.get(data['name'].split('/')[0])
                pool.create(
                    data['name'], params, fstype=getattr(libzfs.DatasetType, data['type']),
                    sparse_vol=sparse, create_ancestors=data['create_ancestors'],
                )
        except libzfs.ZFSException as e:
            self.logger.error('Failed to create dataset', exc_info=True)
            raise CallError(f'Failed to create dataset: {e}')
        else:
            return data

    @accepts(
        Str('id'),
        Dict(
            'dataset_update',
            Dict(
                'properties',
                additional_attrs=True,
            ),
        ),
    )
    def do_update(self, id, data):
        try:
            with libzfs.ZFS() as zfs:
                dataset = zfs.get_dataset(id)

                if 'properties' in data:
                    properties = data['properties'].copy()
                    # Set these after reservations
                    for k in ['quota', 'refquota']:
                        if k in properties:
                            properties[k] = properties.pop(k)  # Set them last
                    self.update_zfs_object_props(properties, dataset)

        except libzfs.ZFSException as e:
            self.logger.error('Failed to update dataset', exc_info=True)
            raise CallError(f'Failed to update dataset: {e}')
        else:
            return data

    def update_zfs_object_props(self, properties, zfs_object):
        verrors = ValidationErrors()
        for k, v in properties.items():
            # If prop already exists we just update it,
            # otherwise create a user property
            prop = zfs_object.properties.get(k)
            if v.get('source') == 'INHERIT':
                if not prop:
                    verrors.add(f'properties.{k}', 'Property does not exist and cannot be inherited')
            else:
                if not any(i in v for i in ('parsed', 'value')):
                    verrors.add(f'properties.{k}', '"value" or "parsed" must be specified when setting a property')
                if not prop and ':' not in k:
                    verrors.add(f'properties.{k}', 'User property needs a colon (:) in its name')

        verrors.check()

        try:
            zfs_object.update_properties(properties)
        except libzfs.ZFSException as e:
            raise CallError(f'Failed to update properties: {e!r}')

    @accepts(
        Str('id'),
        Dict(
            'options',
            Bool('force', default=False),
            Bool('recursive', default=False),
        )
    )
    def do_delete(self, id, options):
        force = options['force']
        recursive = options['recursive']

        args = []
        if force:
            args += ['-f']
        if recursive:
            args += ['-r']

        # If dataset is mounted and has receive_resume_token, we should destroy it or ZFS will say
        # "cannot destroy 'pool/dataset': dataset already exists"
        recv_run = subprocess.run(['zfs', 'recv', '-A', id], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Destroying may take a long time, lets not use py-libzfs as it will block
        # other ZFS operations.
        try:
            subprocess.run(
                ['zfs', 'destroy'] + args + [id], text=True, capture_output=True, check=True,
            )
        except subprocess.CalledProcessError as e:
            if recv_run.returncode == 0 and e.stderr.strip().endswith('dataset does not exist'):
                # This operation might have deleted this dataset if it was created by `zfs recv` operation
                return
            self.logger.error('Failed to delete dataset', exc_info=True)
            error = e.stderr.strip()
            errno_ = errno.EFAULT
            if "Device busy" in error or "dataset is busy" in error:
                errno_ = errno.EBUSY
            raise CallError(f'Failed to delete dataset: {error}', errno_)
        return True

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

    @accepts(Str('id'))
    def hold(self, id):
        """
        Holds snapshot `id`.

        `truenas` tag will be added to the snapshot's tag namespace.
        """
        try:
            with libzfs.ZFS() as zfs:
                snapshot = zfs.get_snapshot(id)
                snapshot.hold('truenas')
        except libzfs.ZFSException as err:
            raise CallError(f'Failed to hold snapshot: {err}')

    @accepts(Str('id'))
    def release(self, id):
        """
        Release held snapshot `id`.

        Will remove all hold tags from the specified snapshot.
        """
        try:
            with libzfs.ZFS() as zfs:
                snapshot = zfs.get_snapshot(id)
                for tag in snapshot.holds:
                    snapshot.release(tag)
        except libzfs.ZFSException as err:
            raise CallError(f'Failed to release snapshot: {err}')
