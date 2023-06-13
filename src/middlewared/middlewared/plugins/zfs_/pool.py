import errno
import libzfs
import os

from middlewared.schema import accepts, Bool, Dict, List, Str
from middlewared.service import CallError, CRUDService, filterable, job
from middlewared.utils import filter_list

from .pool_utils import convert_topology, find_vdev


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
            # Handle `id` or `name` filter specially to avoiding getting every property for all zpools
            if filters and len(filters) == 1 and list(filters[0][:2]) in (['id', '='], ['name', '=']):
                try:
                    pools = [zfs.get(filters[0][2]).asdict(**state_kwargs)]
                except libzfs.ZFSException:
                    pools = []
            else:
                pools = [i.asdict(**state_kwargs) for i in zfs.pools]
        return filter_list(pools, filters, options)

    @accepts(
        Dict(
            'zfspool_create',
            Str('name', required=True),
            List('vdevs', items=[
                Dict(
                    'vdev',
                    Str('root', enum=['DATA', 'CACHE', 'LOG', 'SPARE', 'SPECIAL', 'DEDUP'], required=True),
                    Str(
                        'type', enum=[
                            'DRAID1', 'DRAID2', 'DRAID3', 'RAIDZ1', 'RAIDZ2', 'RAIDZ3', 'MIRROR', 'STRIPE'
                        ], required=True,
                    ),
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
