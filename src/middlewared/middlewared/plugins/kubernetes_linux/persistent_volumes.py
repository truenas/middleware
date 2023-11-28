from middlewared.service import CRUDService, filterable
from middlewared.utils import filter_list

from .k8s import ApiException, PersistentVolume


class KubernetesPersistentVolumesService(CRUDService):

    class Config:
        namespace = 'k8s.pv'
        private = True
        datastore_primary_key_type = 'string'

    @filterable
    async def query(self, filters, options):
        try:
            return filter_list((await PersistentVolume.query())['items'], filters, options)
        except ApiException:
            # We make this safe as it is possible that the cluster does not has csi drivers installed
            # TODO: Makes ure api exception actually handles this case
            return []

    async def do_delete(self, pv_name):
        await PersistentVolume.delete(pv_name)
