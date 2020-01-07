async def interface_post_sync(middleware):
    if not await middleware.call('system.ready'):
        await initialize_kmip_keys(middleware)


async def initialize_kmip_keys(middleware):
    if (await middleware.call('kmip.config'))['enabled']:
        await middleware.call('kmip.initialize_keys')


async def setup(middleware):
    middleware.register_hook('interface.post_sync', interface_post_sync)
    if await middleware.call('system.ready'):
        await initialize_kmip_keys(middleware)
