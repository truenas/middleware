from middlewared.service import Service, private
from middlewared.utils import run
from middlewared.plugins.smb import SMBCmd

import os
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
        if groupmap is None:
            groupmap = (await self.middleware.call('smb.groupmap_list').values())

        conf = await self.middleware.call('smb.config')
        well_known_SID_prefix = "S-1-5-32"
        db_SID = conf['cifs_SID']
        group_SID = None
        groupmap_SID = None
        domain_SID = await self.get_system_sid()
        ret = True
        for group in groupmap:
            group_SID = str(group['SID'])
            if well_known_SID_prefix not in group_SID:
                domain_SID = group_SID.rsplit("-", 1)[0]
                if groupmap_SID is not None and groupmap_SID != domain_SID:
                    self.logger.debug(f"Groupmap table contains more than one unique domain SIDs ({groupmap_SID}) and ({domain_SID})")
                    self.logger.debug('Inconsistent entries in group_mapping.tdb. Situation uncorrectable. Removing corrupted tdb file.')
                    os.unlink(f"{conf['state directory']}/group_mapping.tdb")
                    return False
                else:
                    groupmap_SID = domain_SID

        if db_SID != domain_SID:
            self.logger.debug(f"Domain SID in group_mapping.tdb ({domain_SID}) is not SID in nas config ({db_SID}). Updating db")
            ret = await self.set_database_sid(domain_SID)
            if not ret:
                return ret
            ret = await self.set_system_sid("setlocalsid", domain_SID)

        return ret
