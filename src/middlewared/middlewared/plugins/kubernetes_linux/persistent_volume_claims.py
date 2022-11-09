from middlewared.schema import accepts, Dict, Str
from middlewared.service import CRUDService, filterable
from middlewared.utils import filter_list

from .k8s_new import PersistentVolumeClaim


class KubernetesPersistentVolumeClaimService(CRUDService):

    class Config:
        namespace = 'k8s.pvc'
        namespace_alias = 'k8s.persistent_volume_claim'
        private = True

    @filterable
    async def query(self, filters, options):
        return filter_list((await PersistentVolumeClaim.query())['items'], filters, options)

    @accepts(
        Str('pvc_name'),
        Dict(
            'pvc_delete',
            Str('namespace', required=True),
        )
    )
    async def do_delete(self, pvc_name, options):
        await PersistentVolumeClaim.delete(pvc_name, **options)
        return True
