from middlewared.schema import accepts, Str
from middlewared.service import CRUDService, filterable
from middlewared.utils import filter_list

from .k8s import ZFSVolume


class KubernetesZFSVolumesService(CRUDService):

    NAMESPACE = 'openebs'

    class Config:
        namespace = 'k8s.zv'
        private = True

    @filterable
    async def query(self, filters, options):
        return filter_list((await ZFSVolume.query())['items'], filters, options)

    @accepts(Str('volume_name'))
    async def do_delete(self, volume_name):
        return await ZFSVolume.delete(volume_name, namespace=self.NAMESPACE)
