import errno
import libzfs

from middlewared.service import CallError, Service


def handle_ds_not_found(error_code: int, ds_name: str):
    if error_code == libzfs.Error.NOENT.value:
        raise CallError(f'Dataset {ds_name!r} not found', errno.ENOENT)


class ZFSDatasetService(Service):

    class Config:
        namespace = 'zfs.dataset'
        private = True
        process_pool = True

    def child_dataset_names(self, path):
        # return child datasets given a dataset `path`.
        try:
            with libzfs.ZFS() as zfs:
                return [child.name for child in zfs.get_dataset_by_path(path).children]
        except libzfs.ZFSException as e:
            raise CallError(f'Failed retrieving child datsets for {path} with error {e}')

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
