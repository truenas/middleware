from middlewared.service import CallError, CRUDService, filterable
from middlewared.utils import filter_list

from .k8s import ApiException, StorageClass


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
