from middlewared.service import ConfigService, private


class SMBService(ConfigService):

    class Config:
        datastore = 'services.cifs'
        datastore_extend = 'smb.smb_extend'
        datastore_prefix = 'cifs_srv_'

    @private
    async def smb_extend(self, cifs):
        """Extend cifs for netbios."""
        if not await self.middleware.call('notifier.is_freenas') and self.middleware.call('notifier.failover_node') == 'B':
            cifs['netbiosname'] = cifs['netbiosname_b']
        return cifs
