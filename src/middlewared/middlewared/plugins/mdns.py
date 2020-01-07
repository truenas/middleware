async def interface_post_sync(middleware):
    await middleware.call('etc.generate', 'mdns')


def setup(middleware):
    middleware.register_hook('interface.post_sync', interface_post_sync)
