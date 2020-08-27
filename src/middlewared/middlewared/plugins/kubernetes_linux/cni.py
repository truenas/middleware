from middlewared.service import ConfigService

from .k8s import api_client, service_accounts


class KubernetesCNIService(ConfigService):

    class Config:
        private = True
        namespace = 'k8s.cni'

    async def config(self):
        return {
            'multus': {'service_account': 'multus'},
            'kube_router': {'service_account': 'kube-router'},
        }

    async def setup_cni(self):
        kube_config = await self.middleware.call('kubernetes.config')
        config = await self.config()
        async with api_client() as (api, context):
            cni_config = kube_config['cni_config']
            for cni in config:
                if not await self.validate_cni_integrity(cni, kube_config):
                    cni_config[cni] = await service_accounts.get_service_account_details(
                        context['core_api'], config[cni]['service_account']
                    )

            await self.middleware.call('datastore.update', 'services.kubernetes', kube_config['id'], cni_config)

    async def validate_cni_integrity(self, cni, config=None):
        config = config or await self.middleware.call('kubernetes.config')
        return all(k in (config['cni_config'].get(cni) or {}) for k in ('ca', 'token'))

    async def kube_router_config(self):
        config = await self.middleware.call('kubernetes.config')
        return {
            'cniVersion': '0.3.0',
            'name': 'ix-net',
            'plugins': [
                {
                    'bridge': 'kube-bridge',
                    'ipam': {
                        'subnet': config['cluster_cidr'],
                        'type': 'host-local',
                    },
                    'isDefaultGateway': True,
                    'name': 'kubernetes',
                    'type': 'bridge',
                },
                {
                    'capabilities': {
                        'portMappings': True,
                        'snat': True,
                    },
                    'type': 'portmap',
                },
            ]
        }
