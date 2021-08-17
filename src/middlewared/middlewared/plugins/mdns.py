async def __event_system_ready(middleware, event_type, args):

    if args['id'] == 'ready':
        # start method for service checks whether mDNS is enabled
        await middleware.call("service.start", "mdns")


async def setup(middleware):
    middleware.event_subscribe('system', __event_system_ready)
