from middlewared.service import ServicePartBase


class SysctlInfoBase(ServicePartBase):

    def get_value(self, sysctl_name):
        raise NotImplementedError
