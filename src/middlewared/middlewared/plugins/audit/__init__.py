async def init_audit(middleware, event_type, args):
    if await middleware.call('system.boot_env_first_boot'):
        try:
            await middleware.call("audit.setup")
        except Exception:
            middleware.logger.error("Failed to perform setup tasks for auditing.", exc_info=True)


async def setup(middleware):
    middleware.event_subscribe('system.ready', init_audit)

    try:
        # Set up connections to the auditing databases
        await middleware.call("auditbackend.setup")
    except Exception:
        middleware.logger.error("Failed to set up auditing backend.", exc_info=True)
