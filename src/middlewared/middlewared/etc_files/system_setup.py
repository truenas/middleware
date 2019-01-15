async def render(service, middleware):
    await middleware.call('systemdataset.setup')
    await middleware.call('reporting.sysrrd_disable')
