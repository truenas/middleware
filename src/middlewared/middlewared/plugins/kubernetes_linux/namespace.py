from kubernetes_asyncio import client

from middlewared.schema import Dict
from middlewared.service import accepts, CallError, CRUDService, filterable
from middlewared.utils import filter_list

from .k8s import api_client


class KubernetesNamespaceService(CRUDService):

    class Config:
        namespace = 'k8s.namespace'
        private = True

    @filterable
    async def query(self, filters=None, options=None):
        async with api_client() as (api, context):
            return filter_list(
                [d.to_dict() for d in (await context['core_api'].list_namespace()).items],
                filters, options
            )

    @accepts(
        Dict(
            'namespace_create',
            Dict('body', additional_attrs=True, required=True),
        )
    )
    async def do_create(self, data):
        async with api_client() as (api, context):
            try:
                await context['core_api'].create_namespace(body=data['body'])
            except client.exceptions.ApiException as e:
                raise CallError(f'Unable to create namespace: {e}')
