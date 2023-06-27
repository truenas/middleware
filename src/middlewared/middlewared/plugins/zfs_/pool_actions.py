import errno
import libzfs
import subprocess
import functools

from middlewared.schema import accepts, Bool, Dict, Str
from middlewared.service import CallError, Service

from .pool_utils import find_vdev, SEARCH_PATHS


class ZFSPoolService(Service):

    class Config:
        namespace = 'zfs.pool'
        private = True
        process_pool = True

    @functools.cache
    def get_search_paths(self):
        if self.middleware.call_sync('system.is_ha_capable'):
            # HA capable hardware which means we _ALWAYS_ expect
            # the zpool to have been created with disks that have
            # been formatted with gpt type labels on them
            return ['/dev/disk/by-partuuid']
        return SEARCH_PATHS

    def is_upgraded(self, pool_name):
        enabled = (libzfs.FeatureState.ENABLED, libzfs.FeatureState.ACTIVE)
        with libzfs.ZFS() as zfs:
            try:
                pool = zfs.get(pool_name)
            except libzfs.ZFSException:
                raise CallError(f'{pool_name!r} not found', errno.ENOENT)

            return all((i.state in enabled for i in pool.features))

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
                    raise CallError(f'Failed to find vdev for {label!r}', errno.EINVAL)

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
                        running_scrubs = len([
                            pool for pool in zfs.pools
                            if pool.scrub.state == libzfs.ScanState.SCANNING
                        ])
                        if running_scrubs >= 10:
                            raise CallError(
                                f'{running_scrubs} scrubs are already running. Running too many scrubs simultaneously '
                                'will result in an unresponsive system. Refusing to start scrub.'
                            )

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
            return zfs.get(name).scrub.asdict()

    @accepts()
    def find_import(self):
        sp = self.get_search_paths()
        with libzfs.ZFS() as zfs:
            return [i.asdict() for i in zfs.find_import(search_paths=sp)]

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
            found = None
            sp = self.get_search_paths()
            try:
                for pool in zfs.find_import(cachefile=cachefile, search_paths=sp):
                    if pool.name == name_or_guid or str(pool.guid) == name_or_guid:
                        found = pool
                        break
            except libzfs.ZFSInvalidCachefileException:
                raise CallError('Invalid or missing cachefile', errno.ENOENT)
            except libzfs.ZFSException as e:
                code = errno.ENOENT if e.code == libzfs.Error.NOENT.value else e.code
                raise CallError(str(e), code)
            else:
                if found is None:
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
                return vdev.asdict()
        except libzfs.ZFSException as e:
            raise CallError(str(e))
