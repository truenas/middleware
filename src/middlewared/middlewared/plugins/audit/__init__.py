async def setup(middleware):
    await middleware.call("auditbackend.setup")
