async def __event_system(middleware, event_type, args):
    if args['id'] != 'ready':
        return

    if (await middleware.call('kmip.config'))['enabled']:
        await middleware.call('kmip.initialize_keys')


async def setup(middleware):
    middleware.event_subscribe('system', __event_system)
    if await middleware.call('system.ready'):
        await middleware.call('kmip.initialize_keys')
