import os

from middlewared.service import CallError, Service
from middlewared.utils import run, MIDDLEWARE_RUN_DIR

ZFS_MODULE_PARAMS_PATH = '/sys/module/zfs/parameters'
DEFAULT_ARC_MAX_FILE = f'{MIDDLEWARE_RUN_DIR}/default_arc_max'


class SysctlService(Service):

    class Config:
        private = True

    async def get_value(self, sysctl_name):
        cp = await run(['sysctl', sysctl_name], check=False)
        if cp.returncode:
            raise CallError(f'Unable to retrieve value of "{sysctl_name}" sysctl : {cp.stderr.decode()}')
        return cp.stdout.decode().split('=')[-1].strip()

    def store_default_arc_max(self):
        """This method should be called _BEFORE_ we initialize any VMs
        so that we can capture what the ARC max value was before we start
        changing the various ARC sysctls based on VM memory configurations"""
        val = self.get_arcstats()['c_max']
        try:
            with open(DEFAULT_ARC_MAX_FILE, 'x') as f:
                f.write(str(val))
                f.flush()
        except FileExistsError:
            return self.get_default_arc_max()
        else:
            return val

    def get_default_arc_max(self):
        try:
            with open(DEFAULT_ARC_MAX_FILE) as f:
                return int(f.read())
        except FileNotFoundError:
            return self.store_default_arc_max()

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
        stats = {}
        with open('/proc/spl/kstat/zfs/arcstats') as f:
            for lineno, line in enumerate(f, start=1):
                if lineno > 2:  # skip first 2 lines
                    try:
                        key, _, value = line.strip().split()
                        key, value = key.strip(), value.strip()
                    except ValueError:
                        continue
                    else:
                        stats[key] = int(value) if value.isdigit() else value

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
