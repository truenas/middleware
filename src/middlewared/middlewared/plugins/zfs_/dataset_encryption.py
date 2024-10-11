import libzfs

from middlewared.schema import accepts, Any, Bool, Dict, Int, List, Ref, Str
from middlewared.service import CallError, job, Service
from middlewared.utils import filter_list

from .dataset_utils import flatten_datasets
from .utils import unlocked_zvols_fast, zvol_path_to_name


class ZFSDatasetService(Service):

    class Config:
        namespace = 'zfs.dataset'
        private = True
        process_pool = True

    @accepts(
        Ref('query-filters'),
        Ref('query-options'),
        List(
            'additional_information',
            items=[Str('desideratum', enum=['SIZE', 'RO', 'DEVID', 'ATTACHMENT'])]
        )
    )
    def unlocked_zvols_fast(self, filters, options, additional_information):
        """
        Fast check for zvol information. Supports `additional_information` to
        expand output on an as-needed basis. Adding additional_information to
        the output may impact performance of 'fast' method.
        """

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

    @accepts(
        Str('id'),
        Dict(
            'load_key_options',
            Bool('mount', default=True),
            Bool('recursive', default=False),
            Any('key', default=None, null=True),
            Str('key_location', default=None, null=True),
        ),
    )
    def load_key(self, id_, options):
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

    @accepts(
        Str('id'),
        Dict(
            'check_key',
            Any('key', default=None, null=True),
            Str('key_location', default=None, null=True),
        )
    )
    def check_key(self, id_, options):
        """
        Returns `true` if the `key` is valid, `false` otherwise.
        """
        try:
            with libzfs.ZFS() as zfs:
                ds = zfs.get_dataset(id_)
                self.common_encryption_checks(id_, ds)
                return ds.check_key(**options)
        except libzfs.ZFSException as e:
            self.logger.error(f'Failed to check key for {id_}', exc_info=True)
            raise CallError(f'Failed to check key for {id_}: {e}')

    @accepts(
        Str('id'),
        Dict(
            'unload_key_options',
            Bool('recursive', default=False),
            Bool('force_umount', default=False),
            Bool('umount', default=False),
        )
    )
    def unload_key(self, id_, options):
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

    @accepts(
        Str('id'),
        Dict(
            'change_key_options',
            Dict(
                'encryption_properties',
                Str('keyformat'),
                Str('keylocation'),
                Int('pbkdf2iters')
            ),
            Bool('load_key', default=True),
            Any('key', default=None, null=True),
        ),
    )
    def change_key(self, id_, options):
        try:
            with libzfs.ZFS() as zfs:
                ds = zfs.get_dataset(id_)
                self.common_encryption_checks(id_, ds)
                ds.change_key(props=options['encryption_properties'], load_key=options['load_key'], key=options['key'])
        except libzfs.ZFSException as e:
            self.logger.error(f'Failed to change key for {id_}', exc_info=True)
            raise CallError(f'Failed to change key for {id_}: {e}')

    @accepts(
        Str('id'),
        Dict(
            'change_encryption_root_options',
            Bool('load_key', default=True),
        )
    )
    def change_encryption_root(self, id_, options):
        try:
            with libzfs.ZFS() as zfs:
                ds = zfs.get_dataset(id_)
                ds.change_key(load_key=options['load_key'], inherit=True)
        except libzfs.ZFSException as e:
            raise CallError(f'Failed to change encryption root for {id_}: {e}')

    @accepts(Str('name'), List('params', private=True))
    @job()
    def bulk_process(self, job, name, params):
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
