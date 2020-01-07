from middlewared.service import Service

from .encryption_base import DiskEncryptionBase


class DiskService(Service, DiskEncryptionBase):
    def decrypt(self, job, devices, passphrase=None):
        raise NotImplementedError()
