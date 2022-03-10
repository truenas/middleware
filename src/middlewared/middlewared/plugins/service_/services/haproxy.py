from middlewared.plugins.service_.services.base import SimpleService


class HAProxyService(SimpleService):
    name = 'haproxy'
    etc = ['haproxy']
    systemd_unit = 'haproxy'
