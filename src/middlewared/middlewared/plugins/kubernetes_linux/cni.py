from middlewared.service import Service


class KubernetesCNIService(Service):

    class Config:
        private = True
        namespace = 'k8s.cni'

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
                await self.port_mapping_config(),
            ]
        }

    async def port_mapping_config(self):
        return {
            'capabilities': {
                'portMappings': True,
                'snat': True,
            },
            'type': 'portmap',
        }
