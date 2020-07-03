import errno
import os

from middlewared.service import CallError, Service
from middlewared.utils import run

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

    async def get_pagesize(self):
        cp = await run(['getconf', 'PAGESIZE'], check=False)
        if cp.returncode:
            raise CallError(f'Unable to retrieve pagesize value: {cp.stderr.decode()}')
        return int(cp.stdout.decode().strip())

    def get_arcstats(self):
        path = '/proc/spl/kstat/zfs/arcstats'
        if not os.path.exists(path):
            raise CallError(f'Unable to locate {path}')

        with open(path, 'r') as f:
            data = f.read()

        stats = {}
        for line in filter(lambda l: l and len(l.split()) == 3, map(str.strip, data.split('\n'))):
            key, _type, data = line.split()
            stats[key.strip()] = int(data.strip()) if data.strip().isdigit() else data

        return stats

    def get_arcstats_size(self):
        return self.get_arcstats()['size']
