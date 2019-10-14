import errno
import subprocess
import threading
import time
from collections import defaultdict
from copy import deepcopy
from datetime import datetime

from bsd import geom
import libzfs

from middlewared.alert.base import (
    Alert, AlertCategory, AlertClass, AlertLevel, OneShotAlertClass, SimpleOneShotAlertClass
)
from middlewared.schema import Any, Dict, List, Str, Bool, accepts
from middlewared.service import (
    CallError, CRUDService, ValidationError, ValidationErrors, filterable, job,
)
from middlewared.utils import filter_list, filter_getattrs, start_daemon_thread
from middlewared.validators import ReplicationSnapshotNamingSchema

SCAN_THREADS = {}


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

    @accepts(
        Dict(
            'zfspool_create',
            Str('name', required=True),
            List('vdevs', items=[
                Dict(
                    'vdev',
                    Str('root', enum=['DATA', 'CACHE', 'LOG', 'SPARE'], required=True),
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

        return self.middleware.call_sync('zfs.pool._get_instance', data['name'])

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

    @accepts(Str('pool'))
    def get_disks(self, name):
        disks = self.get_devices(name)

        geom.scan()
        labelclass = geom.class_by_name('LABEL')
        for dev in disks:
            dev = dev.replace('.eli', '')
            find = labelclass.xml.findall(f".//provider[name='{dev}']/../consumer/provider")
            name = None
            if find:
                name = geom.provider_by_id(find[0].get('ref')).geom.name
            else:
                g = geom.geom_by_name('DEV', dev)
                if g:
                    name = g.consumer.provider.geom.name

            if name and (name.startswith('multipath/') or geom.geom_by_name('DISK', name)):
                yield name
            else:
                self.logger.debug(f'Could not find disk for {dev}')

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
    def extend(self, job, name, new=None, existing=None):
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

    @accepts(Str('pool'), Str('label'))
    def detach(self, name, label):
        """
        Detach device `label` from the pool `pool`.
        """
        self.__zfs_vdev_operation(name, label, lambda target: target.detach())

    @accepts(Str('pool'), Str('label'))
    def offline(self, name, label):
        """
        Offline device `label` from the pool `pool`.
        """
        self.__zfs_vdev_operation(name, label, lambda target: target.offline())

    @accepts(
        Str('pool'), Str('label'), Bool('expand', default=False)
    )
    def online(self, name, label, expand=False):
        """
        Online device `label` from the pool `pool`.
        """
        self.__zfs_vdev_operation(name, label, lambda target, *args: target.online(*args), expand)

    @accepts(Str('pool'), Str('label'))
    def remove(self, name, label):
        """
        Remove device `label` from the pool `pool`.
        """
        self.__zfs_vdev_operation(name, label, lambda target: target.remove())

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
    @job(lock=lambda i: f'{i[0]}-{i[1] if len(i) >= 2 else "START"}')
    def scrub(self, job, name, action=None):
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

        def watch():
            while True:
                with libzfs.ZFS() as zfs:
                    scrub = zfs.get(name).scrub.__getstate__()

                if scrub['pause']:
                    job.set_progress(100, 'Scrub paused')
                    break

                if scrub['function'] != 'SCRUB':
                    break

                if scrub['state'] == 'FINISHED':
                    job.set_progress(100, 'Scrub finished')
                    break

                if scrub['state'] == 'CANCELED':
                    break

                if scrub['state'] == 'SCANNING':
                    job.set_progress(scrub['percentage'], 'Scrubbing')
                time.sleep(1)

        if action == 'START':
            t = threading.Thread(target=watch, daemon=True)
            t.start()
            t.join()

    @accepts()
    def find_import(self):
        with libzfs.ZFS() as zfs:
            return [i.__getstate__() for i in zfs.find_import()]

    @accepts(
        Str('name_or_guid'),
        Dict('options', additional_attrs=True),
        Bool('any_host', default=True),
        Str('cachefile', null=True, default=None),
    )
    def import_pool(self, name_or_guid, options, any_host, cachefile):
        found = False
        with libzfs.ZFS() as zfs:
            for pool in zfs.find_import(cachefile=cachefile):
                if pool.name == name_or_guid or str(pool.guid) == name_or_guid:
                    found = pool
                    break

            if not found:
                raise CallError(f'Pool {name_or_guid} not found.', errno.ENOENT)

            zfs.import_pool(found, found.name, options, any_host=any_host)

    @accepts(Str('pool'))
    async def find_not_online(self, pool):
        pool = await self.middleware.call('zfs.pool.query', [['id', '=', pool]], {'get': True})

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

    def flatten_datasets(self, datasets):
        return sum([[deepcopy(ds)] + self.flatten_datasets(ds['children']) for ds in datasets], [])

    @filterable
    def query(self, filters=None, options=None):
        """
        In `query-options` we can provide `extra` arguments which control which data should be retrieved
        for a dataset.

        `query-options.extra.top_level_properties` is a list of properties which we will like to include in the
        top level dict of dataset. It defaults to adding only mountpoint key keeping legacy behavior. If none are
        desired in top level dataset, an empty list should be passed else if null is specified it will add mountpoint
        key to the top level dict if it's present in `query-options.extra.properties` or it's null as well.

        `query-options.extra.properties` is a list of properties which should be retrieved. If null ( by default ),
        it would retrieve all properties, if empty, it will retrieve no property ( `mountpoint` is special in this
        case and is controlled by `query-options.extra.mountpoint` attribute ).

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
        top_level_props = None if extra.get('top_level_properties') is None else extra['top_level_properties'].copy()
        props = extra.get('properties', None)
        flat = extra.get('flat', True)
        user_properties = extra.get('user_properties', True)
        retrieve_properties = extra.get('retrieve_properties', True)
        if not retrieve_properties:
            # This is a short hand version where consumer can specify that they don't want any property to
            # be retrieved
            user_properties = False
            props = []

        with libzfs.ZFS() as zfs:
            # Handle `id` filter specially to avoiding getting all datasets
            if filters and len(filters) == 1 and list(filters[0][:2]) == ['id', '=']:
                state_options = {
                    'snapshots': extra.get('snapshots', False),
                    'recursive': extra.get('recursive', True),
                    'snapshots_recursive': extra.get('snapshots_recursive', False)
                }
                try:
                    datasets = [zfs.get_dataset(filters[0][2]).__getstate__(**state_options)]
                except libzfs.ZFSException:
                    datasets = []
            else:
                datasets = zfs.datasets_serialized(
                    props=props, top_level_props=top_level_props, user_props=user_properties
                )
                if flat:
                    datasets = self.flatten_datasets(datasets)
                else:
                    datasets = list(datasets)

        return filter_list(datasets, filters, options)

    def query_for_quota_alert(self):
        return [
            {
                k: v for k, v in dataset['properties'].items()
                if k in [
                    "name", "quota", "used", "refquota", "usedbydataset", "mounted", "mountpoint",
                    "org.freenas:quota_warning", "org.freenas:quota_critical",
                    "org.freenas:refquota_warning", "org.freenas:refquota_critical"
                ]
            }
            for dataset in self.query()
        ]

    def common_load_dataset_checks(self, ds):
        if not ds.encrypted:
            raise CallError(f'{id} is not encrypted')
        if ds.key_loaded:
            raise CallError(f'{id} key is already loaded')

    @accepts(
        Str('id'),
        Dict(
            'load_key_options',
            Bool('recursive', default=True),
            Any('key', default=None, null=True),
            Str('key_location', default=None, null=True),
        ),
    )
    def load_key(self, id, options):
        try:
            with libzfs.ZFS() as zfs:
                ds = zfs.get_dataset(id)
                self.common_load_dataset_checks(ds)
                ds.load_key(**options)
        except libzfs.ZFSException as e:
            raise CallError(f'Failed to load key for {id}: {e}')

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
                self.common_load_dataset_checks(ds)
                return ds.check_key(**options)
        except libzfs.ZFSException as e:
            raise CallError(f'Failed to check key for {id}: {e}')

    @accepts(Dict(
        'dataset_create',
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

        try:
            with libzfs.ZFS() as zfs:
                pool = zfs.get(data['name'].split('/')[0])
                pool.create(data['name'], params, fstype=getattr(libzfs.DatasetType, data['type']), sparse_vol=sparse)
        except libzfs.ZFSException as e:
            self.logger.error('Failed to create dataset', exc_info=True)
            raise CallError(f'Failed to create dataset: {e}')

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
                    for k, v in data['properties'].items():

                        # If prop already exists we just update it,
                        # otherwise create a user property
                        prop = dataset.properties.get(k)
                        if prop:
                            if v.get('source') == 'INHERIT':
                                prop.inherit(recursive=v.get('recursive', False))
                            elif 'value' in v and (
                                prop.value != v['value'] or prop.source.name == 'INHERITED'
                            ):
                                prop.value = v['value']
                            elif 'parsed' in v and (
                                prop.parsed != v['parsed'] or prop.source.name == 'INHERITED'
                            ):
                                prop.parsed = v['parsed']
                        else:
                            if v.get('source') == 'INHERIT':
                                pass
                            else:
                                if 'value' not in v:
                                    raise ValidationError('properties', f'properties.{k} needs a "value" attribute')
                                if ':' not in k:
                                    raise ValidationError('properties', f'User property needs a colon (:) in its name`')
                                prop = libzfs.ZFSUserProperty(v['value'])
                                dataset.properties[k] = prop

        except libzfs.ZFSException as e:
            self.logger.error('Failed to update dataset', exc_info=True)
            raise CallError(f'Failed to update dataset: {e}')

    def do_delete(self, id, options=None):
        options = options or {}
        force = options.get('force', False)
        recursive = options.get('recursive', False)

        args = []
        if force:
            args += ['-f']
        if recursive:
            args += ['-r']

        # Destroying may take a long time, lets not use py-libzfs as it will block
        # other ZFS operations.
        try:
            subprocess.run(
                ['zfs', 'destroy'] + args + [id], text=True, capture_output=True, check=True,
            )
        except subprocess.CalledProcessError as e:
            self.logger.error('Failed to delete dataset', exc_info=True)
            error = e.stderr.strip()
            errno_ = errno.EFAULT
            if "Device busy" in error:
                errno_ = errno.EBUSY
            raise CallError(f'Failed to delete dataset: {error}', errno_)

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
            raise CallError(str(e))


class ZFSSnapshot(CRUDService):

    class Config:
        namespace = 'zfs.snapshot'
        process_pool = True

    @filterable
    def query(self, filters=None, options=None):
        """
        Query all ZFS Snapshots with `query-filters` and `query-options`.
        """
        # Special case for faster listing of snapshot names (#53149)
        if (
            options and options.get('select') == ['name'] and (
                not filters or
                filter_getattrs(filters).issubset({'name', 'pool'})
            )
        ):
            # Using zfs list -o name is dozens of times faster than py-libzfs
            cmd = ['zfs', 'list', '-H', '-o', 'name', '-t', 'snapshot']
            order_by = options.get('order_by')
            # -s name makes it even faster
            if not order_by or order_by == ['name']:
                cmd += ['-s', 'name']
            cp = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            if cp.returncode != 0:
                raise CallError(f'Failed to retrieve snapshots: {cp.stderr}')
            stdout = cp.stdout.strip()
            if not stdout:
                return []
            snaps = [
                {'name': i, 'pool': i.split('/', 1)[0]}
                for i in stdout.split('\n')
            ]
            if filters:
                return filter_list(snaps, filters, options)
            return snaps
        with libzfs.ZFS() as zfs:
            # Handle `id` filter to avoid getting all snapshots first
            snapshots = []
            if filters and len(filters) == 1 and list(filters[0][:2]) == ['id', '=']:
                try:
                    snapshots.append(zfs.get_snapshot(filters[0][2]).__getstate__())
                except libzfs.ZFSException as e:
                    if e.code != libzfs.Error.NOENT:
                        raise
            else:
                for i in zfs.snapshots:
                    try:
                        snapshots.append(i.__getstate__())
                    except libzfs.ZFSException as e:
                        # snapshot may have been deleted while this is running
                        if e.code != libzfs.Error.NOENT:
                            raise
        # FIXME: awful performance with hundreds/thousands of snapshots
        return filter_list(snapshots, filters, options)

    @accepts(Dict(
        'snapshot_create',
        Str('dataset', required=True, empty=False),
        Str('name', empty=False),
        Str('naming_schema', empty=False, validators=[ReplicationSnapshotNamingSchema()]),
        Bool('recursive', default=False),
        Bool('vmware_sync', default=False),
        Dict('properties', additional_attrs=True),
    ))
    def do_create(self, data):
        """
        Take a snapshot from a given dataset.

        Returns:
            bool: True if succeed otherwise False.
        """

        dataset = data['dataset']
        recursive = data['recursive']
        properties = data['properties']

        verrors = ValidationErrors()

        if 'name' in data and 'naming_schema' in data:
            verrors.add('snapshot_create.naming_schema', 'You can\'t specify name and naming schema at the same time')
        elif 'name' in data:
            name = data['name']
        elif 'naming_schema' in data:
            name = datetime.now().strftime(data['naming_schema'])
        else:
            verrors.add('snapshot_create.naming_schema', 'You must specify either name or naming schema')

        if verrors:
            raise verrors

        vmware_context = None
        if data['vmware_sync']:
            vmware_context = self.middleware.call_sync('vmware.snapshot_begin', dataset, recursive)

        try:
            with libzfs.ZFS() as zfs:
                ds = zfs.get_dataset(dataset)
                ds.snapshot(f'{dataset}@{name}', recursive=recursive, fsopts=properties)

                if vmware_context and vmware_context['vmsynced']:
                    ds.properties['freenas:vmsynced'] = libzfs.ZFSUserProperty('Y')

            self.logger.info(f"Snapshot taken: {dataset}@{name}")
            return True
        except libzfs.ZFSException as err:
            self.logger.error(f"{err}")
            return False
        finally:
            if vmware_context:
                self.middleware.call_sync('vmware.snapshot_end', vmware_context)

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
        Dict('options', Bool('defer', default=False)),
    )
    def do_delete(self, id, options):
        """
        Delete snapshot of name `id`.

        `options.defer` will defer the deletion of snapshot.
        """
        try:
            with libzfs.ZFS() as zfs:
                snap = zfs.get_snapshot(id)
                snap.delete(defer=options['defer'])
        except libzfs.ZFSException as e:
            raise CallError(str(e))

    @accepts(Dict(
        'snapshot_clone',
        Str('snapshot'),
        Str('dataset_dst'),
    ))
    def clone(self, data):
        """
        Clone a given snapshot to a new dataset.

        Returns:
            bool: True if succeed otherwise False.
        """

        snapshot = data.get('snapshot', '')
        dataset_dst = data.get('dataset_dst', '')

        if not snapshot or not dataset_dst:
            return False

        try:
            with libzfs.ZFS() as zfs:
                snp = zfs.get_snapshot(snapshot)
                snp.clone(dataset_dst)
                dataset = zfs.get_dataset(dataset_dst)
                if dataset.type.name == 'FILESYSTEM':
                    dataset.mount_recursive()
            self.logger.info("Cloned snapshot {0} to dataset {1}".format(snapshot, dataset_dst))
            return True
        except libzfs.ZFSException as err:
            self.logger.error("{0}".format(err))
            return False

    @accepts(
        Str('id'),
        Dict(
            'options',
            Bool('recursive', default=False),
            Bool('recursive_clones', default=False),
            Bool('force', default=False),
        ),
    )
    def rollback(self, id, options):
        """
        Rollback to a given snapshot `id`.

        `options.recursive` will destroy any snapshots and bookmarks more recent than the one
        specified.

        `options.recursive_clones` is just like `recursive` but will also destroy any clones.

        `options.force` will force unmount of any clones.
        """
        args = []
        if options['force']:
            args += ['-f']
        if options['recursive']:
            args += ['-r']
        if options['recursive_clones']:
            args += ['-R']

        try:
            subprocess.run(
                ['zfs', 'rollback'] + args + [id], text=True, capture_output=True, check=True,
            )
        except subprocess.CalledProcessError as e:
            raise CallError(f'Failed to rollback snapshot: {e.stderr.strip()}')


class ScanWatch(object):

    def __init__(self, middleware, pool):
        self.middleware = middleware
        self.pool = pool
        self._cancel = threading.Event()

    def run(self):

        while not self._cancel.wait(2):
            with libzfs.ZFS() as zfs:
                scan = zfs.get(self.pool).scrub.__getstate__()
            if scan['state'] == 'SCANNING':
                self.send_scan(scan)
            elif scan['state'] == 'FINISHED':
                # Since this thread finishes on scrub/resilver end the event is sent
                # on devd event arrival
                break

    def send_scan(self, scan=None):
        if not scan:
            with libzfs.ZFS() as zfs:
                scan = zfs.get(self.pool).scrub.__getstate__()
        self.middleware.send_event('zfs.pool.scan', 'CHANGED', fields={
            'scan': scan,
            'name': self.pool,
        })

    def cancel(self):
        self._cancel.set()


class ScrubNotStartedAlertClass(AlertClass, OneShotAlertClass):
    category = AlertCategory.TASKS
    level = AlertLevel.WARNING
    title = "Scrub Failed to Start"
    text = "%s."

    async def create(self, args):
        return Alert(self.__class__, args["text"], _key=args["pool"])

    async def delete(self, alerts, query):
        return list(filter(
            lambda alert: alert.key != query,
            alerts
        ))


class ScrubStartedAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.TASKS
    level = AlertLevel.INFO
    title = "Scrub Started"
    text = "Scrub of pool %r started."


class ScrubFinishedAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.TASKS
    level = AlertLevel.INFO
    title = "Scrub Finished"
    text = "Scrub of pool %r finished."


async def devd_zfs_hook(middleware, data):
    if data.get('type') in ('misc.fs.zfs.resilver_start', 'misc.fs.zfs.scrub_start'):
        pool = data.get('pool_name')
        if not pool:
            return
        if pool in SCAN_THREADS:
            return
        scanwatch = ScanWatch(middleware, pool)
        SCAN_THREADS[pool] = scanwatch
        start_daemon_thread(target=scanwatch.run)

    elif data.get('type') in (
        'misc.fs.zfs.resilver_finish', 'misc.fs.zfs.scrub_finish', 'misc.fs.zfs.scrub_abort',
    ):
        pool = data.get('pool_name')
        if not pool:
            return
        scanwatch = SCAN_THREADS.pop(pool, None)
        if not scanwatch:
            return
        await middleware.run_in_thread(scanwatch.cancel)

        # Send the last event with SCRUB/RESILVER as FINISHED
        await middleware.run_in_thread(scanwatch.send_scan)

    if data.get('type') == 'misc.fs.zfs.scrub_finish':
        await middleware.call('alert.oneshot_delete', 'ScrubFinished', data.get('pool_name'))
        await middleware.call('alert.oneshot_create', 'ScrubFinished', data.get('pool_name'))


def setup(middleware):
    middleware.event_register('zfs.pool.scan', 'Progress of pool resilver/scrub.')
    middleware.register_hook('devd.zfs', devd_zfs_hook)
