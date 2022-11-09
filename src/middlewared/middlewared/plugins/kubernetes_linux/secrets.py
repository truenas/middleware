import yaml

from middlewared.schema import Dict, List, Str
from middlewared.service import accepts, CallError, CRUDService, filterable
from middlewared.utils import filter_list

from .k8s_new import ApiException, Secret


class KubernetesSecretService(CRUDService):

    class Config:
        namespace = 'k8s.secret'
        private = True

    @filterable
    async def query(self, filters, options):
        options = options or {}
        extra = options.get('extra', {})
        kwargs = {
            k: v for k, v in [
                ('labelSelector', extra.get('labelSelector')), ('fieldSelector', extra.get('fieldSelector'))
            ] if v
        }
        if len(filters) == 1 and len(filters[0]) == 3 and list(filters[0])[:2] == ['metadata.namespace', '=']:
            kwargs['namespace'] = filters[0][2]

        return filter_list((await Secret.query(**kwargs))['items'], filters, options)

    @accepts(
        Dict(
            'secret_create',
            Str('namespace', required=True),
            Dict('body', additional_attrs=True, required=True),
            register=True
        )
    )
    async def do_create(self, data):
        try:
            await Secret.create(data['body'], namespace=data['namespace'])
        except ApiException as e:
            raise CallError(f'Unable to create secret: {e}')

    @accepts(
        Str('name'),
        Dict(
            'secret_delete_options',
            Str('namespace', required=True),
        )
    )
    async def do_delete(self, name, options):
        await Secret.delete(name, **options)

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
