import asyncio

from middlewared.service import private, Service


class KubernetesService(Service):

    @private
    def post_start(self):
        # TODO:
        #  We will be tainting node here to make sure pods are not schedule-able / executable
        #  Any kind of migrations will be performed and then finally the taint will be removed from node
        #  so it can run pods
        #  We will also configure multus here after k8s is up and multus service account has been created
        pass


async def _event_system(middleware, event_type, args):

    if args['id'] == 'ready' and (
        await middleware.call('service.query', [['service', '=', 'kubernetes']], {'get': True})
    )['enable']:
        asyncio.ensure_future(middleware.call('service.start', 'kubernetes'))
    elif args['id'] == 'shutdown' and await middleware.call('service.started', 'kubernetes'):
        asyncio.ensure_future(middleware.call('service.stop', 'kubernetes'))


async def setup(middleware):
    middleware.event_subscribe('system', _event_system)
