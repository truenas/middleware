import os

from middlewared.service import CallError, CRUDService, filterable
from middlewared.utils import filter_list

from .k8s_new import ApiException, StorageClass


DEFAULT_STORAGE_CLASS = 'openebs-zfspv-default'


class KubernetesStorageClassService(CRUDService):

    class Config:
        namespace = 'k8s.storage_class'
        private = True
        datastore_primary_key_type = 'string'

    @filterable
    async def query(self, filters, options):
        return filter_list((await StorageClass.query())['items'], filters, options)

    async def do_create(self, data):
        try:
            await StorageClass.create(data)
        except ApiException as e:
            raise CallError(f'Unable to create storage class: {e}')

    async def do_update(self, name, data):
        try:
            await StorageClass.update(name, data)
        except ApiException as e:
            raise CallError(f'Unable to update storage class: {e}')

    async def do_delete(self, name):
        try:
            await StorageClass.delete(name)
        except ApiException as e:
            raise CallError(f'Failed to delete storage class: {e}')

    async def setup_default_storage_class(self):
        try:
            await self.setup_default_storage_class_internal()
        except Exception as e:
            # Let's not make this fatal as workloads managed by us will still be functional
            self.logger.error('Failed to setup default storage class: %s', e)

    async def setup_default_storage_class_internal(self):
        storage_ds = os.path.join((await self.middleware.call('kubernetes.config'))['dataset'], 'default_volumes')
        config = await self.retrieve_storage_class_manifest()
        config['metadata'].update({
            'name': DEFAULT_STORAGE_CLASS,
            'annotations': {'storageclass.kubernetes.io/is-default-class': 'true'},
        })
        config['parameters']['poolname'] = storage_ds
        # Default storage class is going to have delete retain policy
        # We do not want user deployed charts to have leftover hundreds of
        # datasets potentially with time after their relevant charts have been deleted
        config['reclaimPolicy'] = 'Delete'

        if await self.query([
            ['metadata.annotations.storageclass\\.kubernetes\\.io/is-default-class', '=', 'true'],
            ['metadata.name', '=', DEFAULT_STORAGE_CLASS],
        ]):
            await self.middleware.call('k8s.storage_class.delete', DEFAULT_STORAGE_CLASS)

        await self.middleware.call('k8s.storage_class.create', config)

    async def retrieve_storage_class_manifest(self):
        return {
            'apiVersion': 'storage.k8s.io/v1',
            'kind': 'StorageClass',
            'metadata': {
                'name': None,
            },
            'parameters': {'fstype': 'zfs', 'poolname': None, 'shared': 'yes'},
            'provisioner': 'zfs.csi.openebs.io',
            'allowVolumeExpansion': True,
            'reclaimPolicy': 'Retain',
        }
