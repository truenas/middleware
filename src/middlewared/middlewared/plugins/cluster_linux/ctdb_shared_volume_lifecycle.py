async def _event_system_ready(middleware, event_type, args):
    # this soley exists to be called during to
    # ensure that the ctdb shared volume gets
    # FUSE mounted at boot time (if necessary)
    glusterd = await middleware.call(
        'datastore.query', 'services.services',
        [('srv_service', '=', 'glusterd')],
        {'get': True}
    )
    if glusterd['srv_enable']:
        middleware.create_task(middleware.call('service.start', 'glusterd'))


async def _event_system_shutdown(middleware, event_type, args):
    if await middleware.call('service.started', 'glusterd'):
        middleware.create_task(middleware.call('service.stop', 'glusterd'))


async def setup(middleware):
    middleware.event_subscribe('system.ready', _event_system_ready)
    middleware.event_subscribe('system.shutdown', _event_system_shutdown)
