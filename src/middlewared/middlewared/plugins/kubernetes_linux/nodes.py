from kubernetes_asyncio import client
from middlewared.schema import Dict, List, Str
from middlewared.service import accepts, CRUDService, filterable

from .k8s import api_client, nodes


class KubernetesNodeService(CRUDService):

    class Config:
        namespace = 'k8s.node'

    @filterable
    async def query(self, filters=None, options=None):
        async with (await api_client()) as api:
            v1 = client.CoreV1Api(api)
            return [n.to_dict() for n in await v1.list_node_with_http_info()]

    @accepts(
        Str('node_name'),
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
    async def add_taints(self, node_name, taints):
        async with (await api_client(())) as api:
            v1 = client.CoreV1Api(api)
            for taint in taints:
                await nodes.add_taint(v1, taint, node_name=node_name)
