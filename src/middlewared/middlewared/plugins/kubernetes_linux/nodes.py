import asyncio
import contextlib
import yaml

from middlewared.schema import Dict, List, Str
from middlewared.service import accepts, ConfigService

from .k8s import api_client, nodes
from .utils import KUBECONFIG_FILE, KUBERNETES_WORKER_NODE_PASSWORD, NODE_NAME


class KubernetesNodeService(ConfigService):

    class Config:
        namespace = 'k8s.node'
        private = True

    async def config(self):
        try:
            async with api_client({'node': True}) as (api, context):
                return {
                    'node_configured': True,
                    'events': await self.middleware.call('k8s.event.query', [], {
                        'extra': {'field_selector': f'involvedObject.uid={NODE_NAME}'}
                    }),
                    **(context['node'].to_dict())
                }
        except Exception as e:
            return {'node_configured': False, 'error': str(e)}

    def get_cluster_ca(self):
        with contextlib.suppress(FileNotFoundError):
            with open(KUBECONFIG_FILE, 'r') as f:
                config = yaml.safe_load(f.read())

        if config.get('clusters') and isinstance(config.get('clusters'), list):
            if 'cluster' in config['clusters'][0]:
                return config['clusters'][0]['cluster'].get('certificate-authority-data')

    @accepts(
        List(
            'add_taints',
            items=[Dict(
                'taint',
                Str('key', required=True, empty=False),
                Str('value', null=True, default=None),
                Str('effect', required=True, empty=False, enum=['NoSchedule', 'NoExecute'])
            )],
        )
    )
    async def add_taints(self, taints):
        async with api_client({'node': True}) as (api, context):
            for taint in taints:
                await nodes.add_taint(context['core_api'], taint, context['node'])

        remaining_taints = {t['key'] for t in taints}
        timeout = 600
        while remaining_taints and timeout > 0:
            await asyncio.sleep(3)
            timeout -= 3

            config = await self.config()
            if not config['node_configured']:
                break

            remaining_taints -= {t['key'] for t in (config['spec']['taints'] or [])}

    @accepts(
        List('remove_taints', items=[Str('taint_key')]),
    )
    async def remove_taints(self, taint_keys):
        async with api_client({'node': True}) as (api, context):
            for taint_key in taint_keys:
                await nodes.remove_taint(context['core_api'], taint_key, context['node'])

    @accepts()
    async def delete_node(self):
        async with api_client({'node': True}) as (api, context):
            await context['core_api'].delete_node(NODE_NAME)

    @accepts()
    async def worker_node_password(self):
        return KUBERNETES_WORKER_NODE_PASSWORD
