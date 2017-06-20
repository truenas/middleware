from middlewared.schema import accepts
from middlewared.service import ConfigService, private


class SMBService(ConfigService):

    @accepts()
    async def config(self):
        """Returns SMB configuration object."""
        return await self.middleware.call('datastore.config', 'services.cifs', {'extend': 'smb.smb_extend', 'prefix': 'cifs_srv_'})

    @private
    async def smb_extend(self, cifs):
        """Extend cifs for netbios."""
        if not await self.middleware.call('notifier.is_freenas') and self.middleware.call('notifier.failover_node') == 'B':
            cifs['netbiosname'] = cifs['netbiosname_b']
        return cifs
