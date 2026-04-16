import errno
import libzfs
import functools

from middlewared.service import CallError, Service
from .pool_utils import find_vdev, SEARCH_PATHS


class ZFSPoolService(Service):

    class Config:
        namespace = 'zfs.pool'
        private = True

    @functools.cache
    def get_search_paths(self):
        if self.middleware.call_sync('system.is_ha_capable'):
            # HA capable hardware which means we _ALWAYS_ expect
            # the zpool to have been created with disks that have
            # been formatted with gpt type labels on them
            return ['/dev/disk/by-partuuid']
        return SEARCH_PATHS

    def export(self, name: str, options: dict | None = None):
        try:
            with libzfs.ZFS() as zfs:
                # FIXME: force not yet implemented
                pool = zfs.get(name)
                zfs.export_pool(pool)
        except libzfs.ZFSException as e:
            raise CallError(str(e))

    def get_devices(self, name: str):
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

    def detach(self, name: str, label: str, options: dict | None = None):
        """Detach device `label` from the pool `pool`."""
        if options is None:
            options = dict()
        options.setdefault('clear_label', False)
        self.detach_remove_impl('detach', name, label, options)

    def detach_remove_impl(self, op, name, label, options):
        def impl(target):
            getattr(target, op)()
            if options['clear_label']:
                self.clear_label(target.path)
        self.__zfs_vdev_operation(name, label, impl)

    def clear_label(self, device: str):
        """Clear label from `device`."""
        try:
            libzfs.clear_label(device)
        except (libzfs.ZFSException, OSError) as e:
            raise CallError(str(e))

    def offline(self, name: str, label: str):
        """
        Offline device `label` from the pool `pool`.
        """
        self.__zfs_vdev_operation(name, label, lambda target: target.offline())

    def online(self, name: str, label: str, expand: bool = False):
        """
        Online device `label` from the pool `pool`.
        """
        self.__zfs_vdev_operation(name, label, lambda target, *args: target.online(*args), expand)

    def remove(self, name: str, label: str, options: dict | None = None):
        """
        Remove device `label` from the pool `pool`.
        """
        if options is None:
            options = dict()
        options.setdefault('clear_label', False)
        self.detach_remove_impl('remove', name, label, options)

    def replace(self, name: str, label: str, dev: str):
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

    def expand_state(self, name):
        with libzfs.ZFS() as zfs:
            return zfs.get(name).expand.asdict()

    def find_import(self):
        sp = self.get_search_paths()
        with libzfs.ZFS() as zfs:
            return [i.asdict() for i in zfs.find_import(search_paths=sp)]

    def import_pool(
        self,
        name_or_guid: str,
        properties: dict,
        any_host: bool = True,
        cachefile: str | None = None,
        new_name: str | None = None,
        import_options: dict | None = None
    ):
        if import_options is None:
            import_options = dict()
        import_options.setdefault('missing_log', False)

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

    def ddt_prune(self, options):
        if options['percentage'] and options['days']:
            raise CallError('Percentage or days must be provided, not both')
        if options['percentage'] is None and options['days'] is None:
            raise CallError('Percentage or days must be provided')

        try:
            with libzfs.ZFS() as zfs:
                zfs.get(options['pool_name']).ddt_prune(percentage=options['percentage'], days=options['days'])
        except libzfs.ZFSException as e:
            raise CallError(str(e), e.code)
