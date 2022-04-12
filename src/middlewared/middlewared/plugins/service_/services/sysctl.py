from .base import SimpleService


class SysctlService(SimpleService):
    name = 'sysctl'
    etc = ['sysctl']
    systemd_unit = 'systemd-sysctl'
