async def setup(middleware):
    await middleware.call("datastore.setup")
