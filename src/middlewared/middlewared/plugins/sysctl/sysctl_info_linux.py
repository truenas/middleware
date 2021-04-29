import os

from middlewared.service import CallError, Service
from middlewared.utils import run

from .sysctl_info_base import SysctlInfoBase


ZFS_MODULE_PARAMS_PATH = '/sys/module/zfs/parameters'


class SysctlService(Service, SysctlInfoBase):

    class Config:
        private = True

    async def get_value(self, sysctl_name):
        cp = await run(['sysctl', sysctl_name], check=False)
        if cp.returncode:
            raise CallError(f'Unable to retrieve value of "{sysctl_name}" sysctl : {cp.stderr.decode()}')
        return cp.stdout.decode().split('=')[-1].strip()

    def get_arc_max(self):
        return self.get_arcstats()['c_max']

    def get_arc_min(self):
        return self.get_arcstats()['c_min']

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

    async def set_value(self, key, value):
        await run(['sysctl', f'{key}={value}'])

    def write_to_file(self, path, value):
        with open(path, 'w') as f:
            f.write(str(value))

    def set_arc_max(self, value):
        return self.write_to_file(os.path.join(ZFS_MODULE_PARAMS_PATH, 'zfs_arc_max'), value)

    def set_zvol_volmode(self, value):
        return self.write_to_file(os.path.join(ZFS_MODULE_PARAMS_PATH, 'zvol_volmode'), value)
