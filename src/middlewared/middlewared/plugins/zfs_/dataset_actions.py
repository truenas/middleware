import errno
import libzfs

from middlewared.service import CallError, Service
from middlewared.service_exception import ValidationError
from middlewared.plugins.zfs_.utils import path_to_dataset_impl


def handle_ds_not_found(error_code: int, ds_name: str):
    if error_code == libzfs.Error.NOENT.value:
        raise CallError(f'Dataset {ds_name!r} not found', errno.ENOENT)


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
        # NOTE: there is no real reason to call this method
        # since it uses a child process in the process pool.
        # It's more efficient to just import `path_to_dataset_impl`
        # and call it directly.
        return path_to_dataset_impl(path, mntinfo)

    def child_dataset_names(self, path):
        # return child datasets given a dataset `path`.
        try:
            with libzfs.ZFS() as zfs:
                return [child.name for child in zfs.get_dataset_by_path(path).children]
        except libzfs.ZFSException as e:
            raise CallError(f'Failed retrieving child datsets for {path} with error {e}')

    def mount(self, name: str, options: dict | None = None):
        if options is None:
            options = dict()
        options.setdefault('recursive', False)
        options.setdefault('force_mount', False)

        try:
            with libzfs.ZFS() as zfs:
                dataset = zfs.get_dataset(name)
                if options['recursive']:
                    dataset.mount_recursive(ignore_errors=True, force_mount=options['force_mount'])
                else:
                    dataset.mount()
        except libzfs.ZFSException as e:
            self.logger.error('Failed to mount dataset', exc_info=True)
            handle_ds_not_found(e.code, name)
            raise CallError(f'Failed to mount dataset: {e}')

    def umount(self, name: str, options: dict | None = None):
        if options is None:
            options = dict()
        options.setdefault('force', False)

        try:
            with libzfs.ZFS() as zfs:
                dataset = zfs.get_dataset(name)
                dataset.umount(force=options['force'])
        except libzfs.ZFSException as e:
            self.logger.error('Failed to umount dataset', exc_info=True)
            handle_ds_not_found(e.code, name)
            raise CallError(f'Failed to umount dataset: {e}')

    def rename(self, name: str, options: dict):
        options.setdefault('recursive', False)
        options.setdefault('new_name', None)
        if not options['new_name']:
            raise ValidationError('new_name', 'new_name is required')

        try:
            with libzfs.ZFS() as zfs:
                dataset = zfs.get_dataset(name)
                dataset.rename(options['new_name'], recursive=options['recursive'])
        except libzfs.ZFSException as e:
            self.logger.error('Failed to rename dataset', exc_info=True)
            handle_ds_not_found(e.code, name)
            raise CallError(f'Failed to rename dataset: {e}')

    def promote(self, name):
        try:
            with libzfs.ZFS() as zfs:
                dataset = zfs.get_dataset(name)
                dataset.promote()
        except libzfs.ZFSException as e:
            self.logger.error('Failed to promote dataset', exc_info=True)
            handle_ds_not_found(e.code, name)
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
            handle_ds_not_found(e.code, name)

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
