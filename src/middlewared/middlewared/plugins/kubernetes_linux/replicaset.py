from middlewared.service import CRUDService, filterable
from middlewared.utils import filter_list

from .k8s import api_client


class KubernetesReplicaSetService(CRUDService):

    class Config:
        namespace = 'k8s.replicaset'
        private = True

    @filterable
    async def query(self, filters, options):
        async with api_client() as (api, context):
            replica_sets = [
                d.to_dict() for d in (await context['apps_api'].list_replica_set_for_all_namespaces()).items
            ]

        return filter_list(replica_sets, filters, options)
