from kubernetes_asyncio import client
from middlewared.service import CRUDService, filterable

from .k8s import api_client


class KubernetesNodeService(CRUDService):

    class Config:
        namespace = 'k8s.node'

    @filterable
    async def query(self, filters=None, options=None):
        async with (await api_client()) as api:
            v1 = client.CoreV1Api(api)
            return [n.to_dict() for n in await v1.list_node_with_http_info()]
