import asyncio

from .enums import Status


async def _event_system(middleware, event_type, args):
    if args['id'] == 'ready':
        if await middleware.call('failover.licensed'):
            return

        await middleware.call('truecommand.start_truecommand_service')


async def setup(middleware):
    await middleware.call('truecommand.config')
    middleware.event_register('truecommand.config', 'Sent on TrueCommand configuration changes.')

    status = Status((await middleware.call('datastore.config', 'system.truecommand'))['api_key_state'])
    if status == Status.CONNECTED:
        status = Status.CONNECTING

    await middleware.call('truecommand.set_status', status.value)

    middleware.event_subscribe('system', _event_system)
    if await middleware.call('system.ready'):
        if not await middleware.call('failover.licensed'):
            asyncio.ensure_future(middleware.call('truecommand.start_truecommand_service'))
