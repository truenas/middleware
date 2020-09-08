from kubernetes_asyncio import client

from middlewared.schema import Dict, Str
from middlewared.service import accepts, CallError, CRUDService, filterable

from .k8s import api_client


class KubernetesDaemonsetService(CRUDService):

    class Config:
        namespace = 'k8s.daemonset'
        private = True

    @filterable
    async def query(self, filters=None, options=None):
        pass

    @accepts(
        Dict(
            'daemonset_create',
            Str('namespace', required=True),
            Dict('body', additional_attrs=True, required=True),
        )
    )
    async def do_create(self, data):
        async with api_client() as (api, context):
            try:
                context['apps_api'].create_namespaced_daemon_set(namespace=data['namespace'], body=data['body'])
            except client.exceptions.ApiException as e:
                raise CallError(f'Unable to create daemonset: {e}')
