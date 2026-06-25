def render(service, middleware):
    middleware.call_sync2(middleware.services.system.security.configure_fips)
