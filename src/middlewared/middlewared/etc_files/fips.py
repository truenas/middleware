def render(service, middleware):
    middleware.call_sync('system.security.configure_fips')
