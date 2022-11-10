import yaml

from middlewared.schema import accepts, Dict, List, Str

from .k8s_base_resources import KubernetesBaseResource
from .k8s_new import Secret


class KubernetesSecretService(KubernetesBaseResource):

    KUBERNETES_RESOURCE = Secret

    class Config:
        namespace = 'k8s.secret'
        private = True

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
