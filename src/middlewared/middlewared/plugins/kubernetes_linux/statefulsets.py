from middlewared.service import CRUDService, filterable
from middlewared.utils import filter_list

from .k8s_new import StatefulSet


class KubernetesStatefulsetService(CRUDService):

    class Config:
        namespace = 'k8s.statefulset'
        private = True

    @filterable
    async def query(self, filters, options):
        return filter_list((await StatefulSet.query())['items'], filters, options)
