import asyncio


async def _event_system(middleware, event_type, args):
    if args['id'] == 'ready':
        await middleware.call('truecommand.start_truecommand_service')


async def setup(middleware):
    await middleware.call('truecommand.config')
    await middleware.call(
        'truecommand.set_status',
        (await middleware.call('datastore.config', 'system.truecommand'))['api_key_state']
    )

    middleware.event_subscribe('system', _event_system)
    if await middleware.call('system.ready'):
        asyncio.ensure_future(middleware.call('truecommand.start_truecommand_service'))
