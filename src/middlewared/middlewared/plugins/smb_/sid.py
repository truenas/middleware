from middlewared.service import Service, private
from middlewared.utils import run
from middlewared.plugins.smb import SMBCmd

import re

RE_SID = re.compile(r"S-\d-\d+-(\d+-){1,14}\d+$")


class SMBService(Service):

    class Config:
        service = 'cifs'
        service_verb = 'restart'

    @private
    async def get_system_sid(self):
        getSID = await run([SMBCmd.NET.value, "-d", "0", "getlocalsid"], check=False)
        if getSID.returncode != 0:
            self.logger.debug('Failed to retrieve local system SID: %s',
                              getSID.stderr.decode())
            return None

        m = RE_SID.search(getSID.stdout.decode().strip())
        if m:
            return m.group(0)

        self.logger.debug("getlocalsid returned invalid SID: %s",
                          getSID.stdout.decode().strip())
        return None

    @private
    async def set_sid(self, db_sid):
        system_SID = await self.get_system_sid()

        if system_SID == db_sid:
            return True

        if db_sid:
            if not await self.set_system_sid(db_sid):
                self.logger.debug('Unable to set set SID to %s', db_sid)
                return False
        else:
            if not system_SID:
                self.logger.warning('Unable to determine system and database SIDs')
                return False

            await self.set_database_sid(system_SID)
            return True

    @private
    async def set_database_sid(self, SID):
        await self.middleware.call('datastore.update', 'services.cifs', 1, {'cifs_SID': SID})

    @private
    async def set_system_sid(self, SID):
        if not SID:
            return False

        setSID = await run([SMBCmd.NET.value, "-d", "0", "setlocalsid", SID], check=False)
        if setSID.returncode != 0:
            self.logger.debug("setlocalsid failed with error: %s",
                              setSID.stderr.decode())
            return False

        return True

    @private
    async def fixsid(self, groupmap=None):
        """
        Samba generates a new domain sid when its netbios name changes or if samba's secrets.tdb
        has been deleted. passdb.tdb will automatically reflect the new mappings, but the groupmap
        database is not automatically updated in these circumstances. This check is performed when
        synchronizing group mapping database. In case there entries that no longer match our local
        system sid, group_mapping.tdb will be removed and re-generated.
        """
        db_SID = (await self.middleware.call('smb.config'))['cifs_SID']
        system_sid = await self.get_system_sid()

        if db_SID != system_sid:
            self.logger.warning(f"Domain SID in group_mapping.tdb ({system_sid}) is not SID in nas config ({db_SID}). Updating db")
            await self.set_database_sid(system_sid)
