from middlewared.service import CRUDService, filterable
from middlewared.utils import filter_list

from .k8s import api_client


class KubernetesServicesService(CRUDService):

    class Config:
        namespace = 'k8s.service'
        private = True

    @filterable
    async def query(self, filters, options):
        async with api_client() as (api, context):
            return filter_list(
                [
                    d.to_dict() for d in (
                        await context['core_api'].list_service_for_all_namespaces()
                    ).items
                ],
                filters, options
            )
