from .base import SimpleService
from middlewared.utils import run


class SysctlService(SimpleService):
    name = 'sysctl'
    etc = ['sysctl']
    systemd_unit = 'systemd-sysctl'
