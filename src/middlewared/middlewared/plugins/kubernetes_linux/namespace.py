import yaml

from kubernetes_asyncio import client

from middlewared.schema import Dict, List, Str
from middlewared.service import accepts, CallError, CRUDService, filterable
from middlewared.utils import filter_list

from .k8s import api_client


class KubernetesNamespaceService(CRUDService):

    class Config:
        namespace = 'k8s.namespace'
        private = True

    @filterable
    async def query(self, filters, options):
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
            else:
                return await self.query([['metadata.name', '=', data['body']['metadata']['name']]], {'get': True})

    @accepts(
        Str('namespace'),
        Dict(
            'namespace_update',
            Dict('body', additional_attrs=True, required=True),
        )
    )
    async def do_update(self, namespace, data):
        async with api_client() as (api, context):
            try:
                await context['core_api'].patch_namespace(namespace, body=data['body'])
            except client.exceptions.ApiException as e:
                raise CallError(f'Unable to update namespace: {e}')
            else:
                return await self.query([['metadata.name', '=', namespace]], {'get': True})

    @accepts(Str('namespace'))
    async def do_delete(self, namespace):
        async with api_client() as (api, context):
            try:
                await context['core_api'].delete_namespace(namespace)
            except client.exceptions.ApiException as e:
                raise CallError(f'Unable to delete namespace: {e}')
            else:
                return True

    async def namespace_names(self):
        return [n['metadata']['name'] for n in await self.query()]

    @accepts(
        Str('namespace_name'),
        Dict(
            'options',
            List('filters'),
        ),
    )
    async def export_to_yaml(self, namespace_name, options):
        filters = options.get('filters') or []
        filters.append(['metadata.name', '=', namespace_name])
        namespace = await self.query(filters, {'get': True})
        return await self.export_to_yaml_internal(namespace)

    async def export_to_yaml_internal(self, namespace):
        return yaml.dump({
            'apiVersion': 'v1',
            'kind': 'Namespace',
            'metadata': namespace['metadata'],
            'spec': namespace['spec'],
            'status': namespace['status'],
        })
