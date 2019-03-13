async def render(service, middleware):
    await middleware.call('systemdataset.setup')
