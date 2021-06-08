from middlewared.service import CallError, private, Service
from middlewared.utils import run


class DiskService(Service):

    @private
    async def remove_encryption(self, device):
        cp = await run('cryptsetup', 'close', device, check=False, encoding='utf8')
        if cp.returncode:
            raise CallError(f'Failed to close encrypted {device} device mapping : {cp.stderr}')
