from middlewared.plugins.service_.services.base import SimpleService


class HostnameService(SimpleService):
    name = 'hostname'
    freebsd_rc = 'hostname'
