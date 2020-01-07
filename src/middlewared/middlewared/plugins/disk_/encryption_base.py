from middlewared.schema import accepts, List, Str
from middlewared.service import job, ServicePartBase


class DiskEncryptionBase(ServicePartBase):
    @accepts(
        List('devices', items=[Str('device')]),
        Str('passphrase', null=True, default=None, private=True),
    )
    @job(pipes=['input'])
    def decrypt(self, job, devices, passphrase=None):
        """
        Decrypt `devices` using uploaded encryption key
        """
