from middlewared.plugins.service_.services.base import SimpleService


class NetdataService(SimpleService):
    name = 'netdata'

    etc = ['netdata']
    restartable = True

    systemd_unit = 'netdata'
