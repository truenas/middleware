from middlewared.service import CallError, Service
from middlewared.utils import run

from .encryption_base import DiskEncryptionBase


class DiskService(Service, DiskEncryptionBase):
    def decrypt(self, job, devices, passphrase):
        raise NotImplementedError()

    async def remove_encryption(self, device):
        cp = await run('cryptsetup', 'close', device, check=False, encoding='utf8')
        if cp.returncode:
            raise CallError(f'Failed to close encrypted {device} device mapping : {cp.stderr}')
