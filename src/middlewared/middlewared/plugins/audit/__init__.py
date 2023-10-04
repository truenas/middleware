async def setup(middleware):
    try:
        # Set up connections to the auditing databases
        await middleware.call("auditbackend.setup")
    except Exception:
        middleware.logger.error("Failed to set up auditing backend.", exc_info=True)
    if await middleware.call("keyvalue.get", "run_migration", False):
        # If this is an upgrade then free up space used by refreservation on
        # deactivated boot environments
        try:
            await middleware.call("audit.setup")
        except Exception:
            middleware.logger.error("Failed to perform setup tasks for auditing.", exc_info=True)
