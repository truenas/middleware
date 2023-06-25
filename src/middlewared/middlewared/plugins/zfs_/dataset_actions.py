import errno
import libzfs
import os

from middlewared.schema import accepts, Bool, Dict, Str
from middlewared.service import CallError, Service
from middlewared.utils.osc import getmntinfo
from middlewared.utils.path import is_child


class ZFSDatasetService(Service):

    class Config:
        namespace = 'zfs.dataset'
        private = True
        process_pool = True

    def path_to_dataset(self, path, mntinfo=None):
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
        if mntinfo is None:
            mntinfo = getmntinfo(st.st_dev)[st.st_dev]
        else:
            mntinfo = mntinfo[st.st_dev]

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
