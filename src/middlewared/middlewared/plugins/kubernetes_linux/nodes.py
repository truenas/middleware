from kubernetes_asyncio import client
from middlewared.schema import Dict, List, Str
from middlewared.service import accepts, CallError, ConfigService, filterable

from .k8s import api_client, nodes


class KubernetesNodeService(ConfigService):

    class Config:
        namespace = 'k8s.node'

    async def config(self):
        try:
            async with (await api_client()) as api:
                v1 = client.CoreV1Api(api)
                return {'node_configured': True, **((await nodes.get_node(v1)).to_dict())}
        except Exception as e:
            return {'node_configured': False, 'error': str(e)}

    @accepts(
        List(
            'add_taint',
            items=[Dict(
                'taints',
                Str('key', required=True, empty=False),
                Str('value', null=True, default=None),
                Str('effect', required=True, empty=False, enum=['NoSchedule', 'NoExecutable'])
            )],
            default=[],
        )
    )
    async def add_taints(self, taints):
        async with (await api_client(())) as api:
            v1 = client.CoreV1Api(api)
            for taint in taints:
                await nodes.add_taint(v1, taint)
