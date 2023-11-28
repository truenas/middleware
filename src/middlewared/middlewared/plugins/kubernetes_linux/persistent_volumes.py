from middlewared.service import CRUDService, filterable
from middlewared.utils import filter_list

from .k8s import PersistentVolume


class KubernetesPersistentVolumesService(CRUDService):

    class Config:
        namespace = 'k8s.pv'
        private = True
        datastore_primary_key_type = 'string'

    @filterable
    async def query(self, filters, options):
        return filter_list((await PersistentVolume.query())['items'], filters, options)

    async def do_delete(self, pv_name):
        await PersistentVolume.delete(pv_name)
