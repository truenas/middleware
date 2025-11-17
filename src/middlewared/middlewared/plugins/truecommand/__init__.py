from middlewared.api.current import TruecommandStatus


async def _event_system_ready(middleware, event_type, args):
    if await middleware.call('failover.licensed'):
        return

    await middleware.call('truecommand.start_truecommand_service')


async def setup(middleware):
    await middleware.call('truecommand.config')

    status = TruecommandStatus((await middleware.call('datastore.config', 'system.truecommand'))['api_key_state'])
    if status == TruecommandStatus.CONNECTED:
        status = TruecommandStatus.CONNECTING

    await middleware.call('truecommand.set_status', status.value)

    middleware.event_subscribe('system.ready', _event_system_ready)
    if await middleware.call('system.ready'):
        if not await middleware.call('failover.licensed'):
            middleware.create_task(middleware.call('truecommand.start_truecommand_service'))
