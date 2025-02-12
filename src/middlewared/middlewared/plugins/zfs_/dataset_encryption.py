import libzfs

from middlewared.service import CallError, job, Service
from middlewared.utils import filter_list

from .dataset_utils import flatten_datasets
from .utils import unlocked_zvols_fast, zvol_path_to_name


class ZFSDatasetService(Service):

    class Config:
        namespace = 'zfs.dataset'
        private = True
        process_pool = True

    def unlocked_zvols_fast(
        self,
        filters: list | None = None,
        options: dict | None = None,
        additional_information: list | None = None
    ):
        """
        Fast check for zvol information. Supports `additional_information` to
        expand output on an as-needed basis. Adding additional_information to
        the output may impact performance of 'fast' method.
        """
        if filters is None:
            filters = []
        if options is None:
            options = dict()
        if additional_information is None:
            additional_information = []

        def get_attachments():
            extents = self.middleware.call_sync(
                'iscsi.extent.query', [('type', '=', 'DISK')], {'select': ['path', 'type']}
            )
            iscsi_zvols = {
                zvol_path_to_name('/dev/' + i['path']): i for i in extents
            }

            vm_devices = self.middleware.call_sync('vm.device.query', [['dtype', '=', 'DISK']])
            vm_zvols = {
                zvol_path_to_name(i['attributes']['path']): i for i in vm_devices
            }

            instance_zvols = {}
            for instance in self.middleware.call_sync('virt.instance.query'):
                for device in self.middleware.call_sync('virt.instance.device_list', instance['id']):
                    if device['dev_type'] != 'DISK':
                        continue
                    if not device['source'] or not device['source'].startswith('/dev/zvol/'):
                        continue
                    # Remove /dev/zvol/ from source
                    instance_zvols[device['source'][10:]] = instance
            return {
                'iscsi.extent.query': iscsi_zvols,
                'vm.devices.query': vm_zvols,
                'virt.instance.query': instance_zvols,
            }

        data = {}
        if 'ATTACHMENT' in additional_information:
            data['attachments'] = get_attachments()

        zvol_list = list(unlocked_zvols_fast(additional_information, data).values())
        return filter_list(zvol_list, filters, options)

    def locked_datasets(self, names=None):
        query_filters = []
        if names is not None:
            names_optimized = []
            for name in sorted(names, key=len):
                if not any(name.startswith(f'{existing_name}/') for existing_name in names_optimized):
                    names_optimized.append(name)

            query_filters.append(['id', 'in', names_optimized])

        result = flatten_datasets(self.middleware.call_sync('zfs.dataset.query', query_filters, {
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
                self.middleware.call_sync('zfs.dataset.mount', id_, {'recursive': recursive})

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

    def unload_key(self, id_: str, options: dict | None = None):
        if options is None:
            options = {
                'recursive': False,
                'force_umount': False,
                'umount': False,
            }
        options.setdefault('recursive', False)
        options.setdefault('force_umount', False)
        options.setdefault('umount', False)

        force = options.pop('force_umount')
        if options.pop('umount') and self.middleware.call_sync(
                'zfs.dataset.query', [['id', '=', id_]], {'extra': {'retrieve_children': False}, 'get': True}
        )['properties'].get('mountpoint', {}).get('value', 'none') != 'none':
            self.middleware.call_sync('zfs.dataset.umount', id_, {'force': force})
        try:
            with libzfs.ZFS() as zfs:
                ds = zfs.get_dataset(id_)
                self.common_encryption_checks(id_, ds)
                if not ds.key_loaded:
                    raise CallError(f'{id_}\'s key is not loaded')
                ds.unload_key(**options)
        except libzfs.ZFSException as e:
            self.logger.error(f'Failed to unload key for {id_}', exc_info=True)
            raise CallError(f'Failed to unload key for {id_}: {e}')

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
