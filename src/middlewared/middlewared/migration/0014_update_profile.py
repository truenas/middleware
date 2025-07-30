async def migrate(middleware):
    if await middleware.call("system.is_enterprise"):
        await middleware.call("update.set_profile", "MISSION_CRITICAL")
