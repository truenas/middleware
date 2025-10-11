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

    def promote(self, name):
        try:
            with libzfs.ZFS() as zfs:
                dataset = zfs.get_dataset(name)
                dataset.promote()
        except libzfs.ZFSException as e:
            self.logger.error('Failed to promote dataset', exc_info=True)
            handle_ds_not_found(e.code, name)
            raise CallError(f'Failed to promote dataset: {e}')
