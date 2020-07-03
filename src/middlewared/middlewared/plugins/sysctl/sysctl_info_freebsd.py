import errno
import sysctl

from middlewared.service import CallError, Service

from .sysctl_info_base import SysctlInfoBase


class SysctlService(Service, SysctlInfoBase):

    class Config:
        private = True

    def get_value(self, sysctl_name):
        var = sysctl.filter(sysctl_name)
        if var:
            return var[0].value
        else:
            raise CallError(f'"{sysctl_name}" sysctl could not be found', errno.ENOENT)
