import re

from middlewared.service import Service
from middlewared.utils import run


RE_VENDOR = re.compile(r'description:\s*VGA compatible controller[\s\S]*vendor:\s*(.*)')


class DeviceService(Service):

    GPU = None

    async def available_gpu(self):
        if self.GPU:
            return self.GPU

        not_available = {'available': False, 'vendor': None}
        cp = await run(['lshw', '-numeric', '-C', 'display'], check=False)
        if cp.returncode:
            self.logger.error('Unable to retrieve GPU details: %s', cp.stderr.decode())
            return not_available

        vendor = RE_VENDOR.findall(cp.stdout.decode())
        if not vendor:
            self.GPU = not_available
        else:
            # We only support nvidia based GPU's right now based on equipment available
            if 'nvidia' in vendor[0].lower():
                self.GPU = {'available': True, 'vendor': 'NVIDIA'}
            else:
                self.GPU = not_available
        return self.GPU
