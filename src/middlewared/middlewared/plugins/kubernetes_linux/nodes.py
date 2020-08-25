from kubernetes_asyncio import client
from middlewared.schema import Dict, List, Str
from middlewared.service import accepts, ConfigService

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
            'add_taints',
            items=[Dict(
                'taint',
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
            node = await nodes.get_node(v1)
            for taint in taints:
                await nodes.add_taint(v1, taint, node)

    @accepts(
        List('remove_taints', items=[Str('taint_key')]),
    )
    async def remove_taints(self, taint_keys):
        async with (await api_client(())) as api:
            v1 = client.CoreV1Api(api)
            node = await nodes.get_node(v1)
            for taint_key in taint_keys:
                await nodes.remove_taint(v1, taint_key, node)
