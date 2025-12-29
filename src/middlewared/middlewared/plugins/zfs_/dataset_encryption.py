import libzfs

from middlewared.service import CallError, job, Service


class ZFSDatasetService(Service):

    class Config:
        namespace = 'zfs.dataset'
        private = True
        process_pool = True

    def common_load_dataset_checks(self, id_, ds):
        self.common_encryption_checks(id_, ds)
        if ds.key_loaded:
            raise CallError(f'{id_} key is already loaded')

    def common_encryption_checks(self, id_, ds):
        if not ds.encrypted:
            raise CallError(f'{id_} is not encrypted')

    def load_key(self, id_: str, options: dict | None = None):
        if options is None:
            options = {
                'mount': True,
                'recursive': False,
                'key': None,
                'key_location': None,
            }
        options.setdefault('mount', True)
        options.setdefault('recursive', False)
        options.setdefault('key', None)
        options.setdefault('key_location', None)

        mount_ds = options.pop('mount')
        recursive = options.pop('recursive')
        try:
            with libzfs.ZFS() as zfs:
                ds = zfs.get_dataset(id_)
                self.common_load_dataset_checks(id_, ds)
                ds.load_key(**options)
        except libzfs.ZFSException as e:
            self.logger.error(f'Failed to load key for {id_}', exc_info=True)
            raise CallError(f'Failed to load key for {id_}: {e}')
        else:
            if mount_ds:
                self.call_sync2(self.s.zfs.resource.mount, id_, recursive=recursive)

    def check_key(self, id_: str, options: dict | None = None):
        """
        Returns `true` if the `key` is valid, `false` otherwise.
        """
        if options is None:
            options = {
                'key': None,
                'key_location': None,
            }

        try:
            with libzfs.ZFS() as zfs:
                ds = zfs.get_dataset(id_)
                self.common_encryption_checks(id_, ds)
                return ds.check_key(**options)
        except libzfs.ZFSException as e:
            self.logger.error(f'Failed to check key for {id_}', exc_info=True)
            raise CallError(f'Failed to check key for {id_}: {e}')

    def change_key(self, id_: str, options: dict | None = None):
        if options is None:
            options = {
                'encryption_properties': {},
                'load_key': True,
                'key': None,
            }

        try:
            with libzfs.ZFS() as zfs:
                ds = zfs.get_dataset(id_)
                self.common_encryption_checks(id_, ds)
                ds.change_key(props=options['encryption_properties'], load_key=options['load_key'], key=options['key'])
        except libzfs.ZFSException as e:
            self.logger.error(f'Failed to change key for {id_}', exc_info=True)
            raise CallError(f'Failed to change key for {id_}: {e}')

    def change_encryption_root(self, id_: str, options: dict | None = None):
        if options is None:
            options = {'load_key': True}

        try:
            with libzfs.ZFS() as zfs:
                ds = zfs.get_dataset(id_)
                ds.change_key(load_key=options['load_key'], inherit=True)
        except libzfs.ZFSException as e:
            raise CallError(f'Failed to change encryption root for {id_}: {e}')

    @job()
    def bulk_process(self, job, name: str, params: list):
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
