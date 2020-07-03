from middlewared.service import ServicePartBase


class SysctlInfoBase(ServicePartBase):

    def get_value(self, sysctl_name):
        raise NotImplementedError

    def get_arc_max(self):
        raise NotImplementedError

    def get_arc_min(self):
        raise NotImplementedError

    def get_pagesize(self):
        raise NotImplementedError

    def get_arcstats_size(self):
        raise NotImplementedError

    def get_arcstats(self):
        raise NotImplementedError
