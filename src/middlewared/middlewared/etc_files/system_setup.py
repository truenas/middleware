async def render(service, middleware):
    await middleware.call('systemdataset.setup')
    await middleware.call('systemdataset.sysrrd_disable')
    if not await middleware.call('notifier.pwenc_check'):
        await middleware.call('notifier.pwenc_generate_secret')
