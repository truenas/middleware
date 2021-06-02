import yaml

from kubernetes_asyncio import client

from middlewared.schema import Dict, List, Ref, Str
from middlewared.service import accepts, CallError, CRUDService, filterable
from middlewared.utils import filter_list

from .k8s import api_client


class KubernetesSecretService(CRUDService):

    class Config:
        namespace = 'k8s.secret'
        private = True

    @filterable
    async def query(self, filters, options):
        options = options or {}
        label_selector = options.get('extra', {}).get('label_selector')
        kwargs = {k: v for k, v in [('label_selector', label_selector)] if v}
        async with api_client() as (api, context):
            return filter_list(
                [d.to_dict() for d in (await context['core_api'].list_secret_for_all_namespaces(**kwargs)).items],
                filters, options
            )

    @accepts(
        Dict(
            'secret_create',
            Str('namespace', required=True),
            Dict('body', additional_attrs=True, required=True),
            register=True
        )
    )
    async def do_create(self, data):
        async with api_client() as (api, context):
            try:
                await context['core_api'].create_namespaced_secret(
                    namespace=data['namespace'], body=data['body']
                )
            except client.exceptions.ApiException as e:
                raise CallError(f'Unable to create secret: {e}')
            else:
                return await self.query([
                    ['metadata.name', '=', data['metadata.name']],
                    ['metadata.namespace', '=', data['namespace']],
                ], {'get': True})

    @accepts(
        Str('name'),
        Ref('secret_create'),
    )
    async def do_update(self, name, data):
        async with api_client() as (api, context):
            try:
                await context['core_api'].patch_namespaced_secret(
                    name, namespace=data['namespace'], body=data['body']
                )
            except client.exceptions.ApiException as e:
                raise CallError(f'Unable to patch {name} secret: {e}')
            else:
                return await self.query([
                    ['metadata.name', '=', name],
                    ['metadata.namespace', '=', data['namespace']],
                ], {'get': True})

    @accepts(
        Str('name'),
        Dict(
            'secret_delete_options',
            Str('namespace', required=True),
        )
    )
    async def do_delete(self, name, options):
        async with api_client() as (api, context):
            try:
                await context['core_api'].delete_namespaced_secret(name, options['namespace'])
            except client.exceptions.ApiException as e:
                raise CallError(f'Unable to delete secret: {e}')
            else:
                return True

    @accepts(
        Str('secret_name'),
        Dict(
            'options',
            List('filters'),
        ),
    )
    async def export_to_yaml(self, secret_name, options):
        filters = options.get('filters') or []
        filters.append(['metadata.name', '=', secret_name])
        secret = await self.query(filters, {'get': True})
        return await self.export_to_yaml_internal(secret)

    async def export_to_yaml_internal(self, secret):
        return yaml.dump({
            'apiVersion': 'v1',
            'data': secret['data'],
            'kind': 'Secret',
            'metadata': secret['metadata'],
            'type': secret['type'],
        })
