async def render(service, middleware):
    await middleware.call('systemdataset.setup')
    if not await middleware.call('notifier.pwenc_check'):
        await middleware.call('notifier.pwenc_generate_secret')
