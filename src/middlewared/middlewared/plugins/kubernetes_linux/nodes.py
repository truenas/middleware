from middlewared.schema import Dict, List, Str
from middlewared.service import accepts, ConfigService

from .k8s import api_client, nodes


class KubernetesNodeService(ConfigService):

    class Config:
        namespace = 'k8s.node'

    async def config(self):
        try:
            async with api_client({'node': True}) as (api, context):
                return {'node_configured': True, **(context['node'].to_dict())}
        except Exception as e:
            return {'node_configured': False, 'error': str(e)}

    @accepts(
        List(
            'add_taints',
            items=[Dict(
                'taint',
                Str('key', required=True, empty=False),
                Str('value', null=True, default=None),
                Str('effect', required=True, empty=False, enum=['NoSchedule', 'NoExecute'])
            )],
            default=[],
        )
    )
    async def add_taints(self, taints):
        async with api_client({'node': True}) as (api, context):
            for taint in taints:
                await nodes.add_taint(context['core_api'], taint, context['node'])

    @accepts(
        List('remove_taints', items=[Str('taint_key')]),
    )
    async def remove_taints(self, taint_keys):
        async with api_client({'node': True}) as (api, context):
            for taint_key in taint_keys:
                await nodes.remove_taint(context['core_api'], taint_key, context['node'])
