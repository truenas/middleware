import libzfs

from middlewared.service import CallError, job, Service
from middlewared.utils import filter_list
from middlewared.plugins.zfs.mount_unmount_impl import MountArgs, UnmountArgs

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

            namespaces = self.middleware.call_sync(
                'nvmet.namespace.query', [['device_type', '=', 'ZVOL']], {'select': ['device_path']}
            )
            nvmet_zvols = {
                zvol_path_to_name('/dev/' + i['device_path']): i for i in namespaces
            }
            return {
                'iscsi.extent.query': iscsi_zvols,
                'vm.devices.query': vm_zvols,
                'virt.instance.query': instance_zvols,
                'nvmet.namespace.query': nvmet_zvols,
            }

        data = {}
        if 'ATTACHMENT' in additional_information:
            data['attachments'] = get_attachments()

        zvol_list = list(unlocked_zvols_fast(additional_information, data).values())
        return filter_list(zvol_list, filters, options)

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
                self.middleware.call_sync(
                    'zfs.resource.mount',
                    MountArgs(filesystem=id_, recursive=recursive)
                )

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
                'recursive': True,
                'force_umount': False,
            }
        options.setdefault('recursive', True)
        options.setdefault('force_umount', False)
        force = options.pop('force_umount')
        # though libzfs upstream is written in a way
        # that makes it seem as-if you can unload the
        # key for an encrypted dataset WITHOUT unmounting
        # it, this is false. You have to unmount the
        # dataset before you can unload the key.
        self.middleware.call_sync(
            'zfs.resource.unmount',
            UnmountArgs(
                filesystem=id_,
                recursive=options['recursive'],
                force=force,
                unload_encryption_key=True
            )
        )

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
