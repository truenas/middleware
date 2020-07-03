import errno
import sysctl

from middlewared.service import CallError, Service
from middlewared.utils import run

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

    def get_arc_max(self):
        return self.get_value('vfs.zfs.arc.max')

    def get_arc_min(self):
        return self.get_value('vfs.zfs.arc.min')

    def get_pagesize(self):
        return self.get_value('hw.pagesize')

    async def get_arcstats(self):
        cp = await run(['sysctl', 'kstat.zfs.misc.arcstats'], check=False)
        if cp.returncode:
            raise CallError(f'Failed to retrieve arcstats: {cp.stderr.decode()}')

        stats = {}
        for line in filter(lambda l: l and ':' in l, map(str.strip, cp.stdout.decode().split('\n'))):
            key, value = line.split(':')
            stats[key.strip().split('.')[-1]] = int(value.strip()) if value.strip().isdigit() else value

        return stats

    def get_arcstats_size(self):
        return self.get_value('kstat.zfs.misc.arcstats.size')

    def set_value(self, key, value):
        var = sysctl.filter(key)
        if var:
            var[0].value = value
        else:
            raise CallError(f'"{key}" sysctl could not be found', errno.ENOENT)

    def set_arc_max(self, value):
        return self.set_value('vfs.zfs.arc.max', value)
