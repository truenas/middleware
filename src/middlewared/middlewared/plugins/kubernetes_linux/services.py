from kubernetes_asyncio import client

from middlewared.service import accepts, CallError, CRUDService, filterable
from middlewared.schema import Dict, Str
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

    @accepts(
        Str('name'),
        Dict(
            'service_delete_options',
            Str('namespace', required=True),
        )
    )
    async def do_delete(self, name, options):
        async with api_client() as (api, context):
            try:
                await context['core_api'].delete_namespaced_service(name, options['namespace'])
            except client.exceptions.ApiException as e:
                raise CallError(f'Unable to delete service: {e}')
            else:
                return True
