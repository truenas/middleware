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

    async def set_value(self, key, value):
        await run(['sysctl', f'{key}={value}'])

    def write_to_file(self, path, value):
        with open(path, 'w') as f:
            f.write(str(value))

    def set_zvol_volmode(self, value):
        return self.write_to_file(os.path.join(ZFS_MODULE_PARAMS_PATH, 'zvol_volmode'), value)
