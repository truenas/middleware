import asyncio


async def _event(middleware, event_type, args):

    if args['id'] == 'ready':
        # this soley exists to be called during to
        # ensure that the ctdb shared volume gets
        # FUSE mounted at boot time (if necessary)
        glusterd = await middleware.call(
            'datastore.query', 'services.services',
            [('srv_service', '=', 'glusterd')],
            {'get': True}
        )
        if glusterd['srv_enable']:
            asyncio.ensure_future(middleware.call('service.start', 'glusterd'))
    elif args['id'] == 'shutdown' and await middleware.call('service.started', 'glusterd'):
        asyncio.ensure_future(middleware.call('service.stop', 'glusterd'))


async def setup(middleware):
    middleware.event_subscribe('system', _event)
