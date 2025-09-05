def render(service, middleware):
    middleware.logger.debug('Made it here')
    middleware.call_sync('system.security.configure_fips')
