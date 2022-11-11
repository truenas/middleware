import yaml

from middlewared.schema import Dict, List, Str
from middlewared.service import accepts, CallError, CRUDService, filterable
from middlewared.utils import filter_list

from .k8s_new import ApiException, Namespace


class KubernetesNamespaceService(CRUDService):

    class Config:
        namespace = 'k8s.namespace'
        private = True

    @filterable
    async def query(self, filters, options):
        return filter_list((await Namespace.query())['items'], filters, options)

    @accepts(
        Dict(
            'namespace_create',
            Dict('body', additional_attrs=True, required=True),
        )
    )
    async def do_create(self, data):
        try:
            await Namespace.create(data['body'])
        except ApiException as e:
            raise CallError(f'Unable to create namespace: {e}')

    @accepts(
        Str('namespace'),
        Dict(
            'namespace_update',
            Dict('body', additional_attrs=True, required=True),
        )
    )
    async def do_update(self, namespace, data):
        try:
            await Namespace.update(namespace, data['body'])
        except ApiException as e:
            raise CallError(f'Unable to update namespace: {e}')

    @accepts(Str('namespace'))
    async def do_delete(self, namespace):
        try:
            await Namespace.delete(namespace)
        except ApiException as e:
            raise CallError(f'Unable delete namespace: {e}')
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
