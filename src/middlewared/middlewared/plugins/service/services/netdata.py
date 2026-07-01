from middlewared.plugins.service.services.base import SimpleService


class NetdataService(SimpleService):
    name = 'netdata'

    etc = ['netdata']
    restartable = True
    may_run_on_standby = False

    systemd_unit = 'netdata'
