from middlewared.plugins.service_.services.base import SimpleService


class RoutingService(SimpleService):
    name = 'routing'
    freebsd_rc = 'routing'
