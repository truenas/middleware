import asyncio

from middlewared.service import private, Service

from .k8s import api_client, service_accounts


class KubernetesService(Service):

    @private
    async def post_start(self):
        # TODO:
        #  We will be tainting node here to make sure pods are not schedule-able / executable
        #  Any kind of migrations will be performed and then finally the taint will be removed from node
        #  so it can run pods
        #  We will also configure multus here after k8s is up and multus service account has been created
        await self.middleware.call(
            'k8s.node.add_taints', [{'key': 'ix-taint', 'effect': e} for e in ('NoSchedule', 'NoExecute')]
        )
        await self.configure_multus()

    @private
    async def configure_multus(self):
        config = await self.middleware.call('kubernetes.config')
        if not all(k in (config['multus_config'] or {}) for k in ('ca', 'token')):
            async with api_client() as (api, context):
                while True:
                    try:
                        svc_account = await service_accounts.get_service_account(context['core_api'], 'multus')
                    except Exception:
                        # TODO: Let's handle this gracefully with events please
                        await asyncio.sleep(5)
                    else:
                        break
                account_details = await service_accounts.get_service_account_tokens_cas(
                    context['core_api'], svc_account
                )
                await self.middleware.call(
                    'datastore.update', 'services.kubernetes', config['id'], {'multus_config': account_details[0]}
                )
        await self.middleware.call('etc.generate', 'multus')


async def _event_system(middleware, event_type, args):

    if args['id'] == 'ready' and (
        await middleware.call('service.query', [['service', '=', 'kubernetes']], {'get': True})
    )['enable']:
        asyncio.ensure_future(middleware.call('service.start', 'kubernetes'))
    elif args['id'] == 'shutdown' and await middleware.call('service.started', 'kubernetes'):
        asyncio.ensure_future(middleware.call('service.stop', 'kubernetes'))


async def setup(middleware):
    middleware.event_subscribe('system', _event_system)
