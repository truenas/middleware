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
        try:
            return filter_list((await StorageClass.query())['items'], filters, options)
        except ApiException:
            # We make this safe as it is possible that the cluster does not has csi drivers installed
            return []

    async def do_delete(self, name):
        try:
            await StorageClass.delete(name)
        except ApiException as e:
            raise CallError(f'Failed to delete storage class: {e}')
