import subprocess

from middlewared.service import Service, private
from middlewared.service_exception import CallError
from middlewared.utils.functools_ import cache
from middlewared.utils.sid import random_sid
from .constants import SMBCmd


class SMBService(Service):

    class Config:
        service = 'cifs'
        service_verb = 'restart'

    @cache
    @private
    def local_server_sid(self):
        if (db_sid := self.middleware.call_sync('smb.config')['cifs_SID']):
            return db_sid

        new_sid = random_sid()
        self.middleware.call_sync('datastore.update', 'services.cifs', 1, {'cifs_SID': new_sid})
        return new_sid

    @private
    def set_system_sid(self):
        server_sid = self.local_server_sid()

        setsid = subprocess.run([
            SMBCmd.NET.value, '-d', '0',
            'setlocalsid', server_sid,
        ], capture_output=True, check=False)

        if setsid.returncode != 0:
            raise CallError(f'setlocalsid failed: {setsid.stderr.decode()}')
