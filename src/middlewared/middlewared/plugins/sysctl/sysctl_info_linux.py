import errno
import os

from middlewared.service import CallError, Service

from .sysctl_info_base import SysctlInfoBase


ZFS_MODULE_PARAMS_PATH = '/sys/module/zfs/parameters'


class SysctlService(Service, SysctlInfoBase):

    def get_value(self, sysctl_name):
        raise NotImplementedError

    def not_found_error(self, name):
        raise CallError(f'"{name}" sysctl could not be found', errno.ENOENT)

    def get_arc_max(self):
        return int(self.read_value_from_file(os.path.join(ZFS_MODULE_PARAMS_PATH, 'zfs_arc_max'), 'zfs_arc_max'))

    def get_arc_min(self):
        return int(self.read_value_from_file(os.path.join(ZFS_MODULE_PARAMS_PATH, 'zfs_arc_min'), 'zfs_arc_min'))

    def read_value_from_file(self, path, name):
        if os.path.exists(path):
            with open(path, 'r') as f:
                return f.read().strip()
        else:
            self.not_found_error(name)
