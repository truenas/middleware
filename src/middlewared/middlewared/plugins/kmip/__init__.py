async def initialize_kmip_keys(middleware):
    if (await middleware.call('kmip.config'))['enabled']:
        await middleware.call('kmip.initialize_keys')


async def __event_system_ready(middleware, event_type, args):
    if args['id'] == 'ready':
        await initialize_kmip_keys(middleware)


async def setup(middleware):
    await middleware.call('network.general.register_activity', 'kmip', 'KMIP')
    middleware.event_subscribe('system', __event_system_ready)
    if await middleware.call('system.ready'):
        await initialize_kmip_keys(middleware)
