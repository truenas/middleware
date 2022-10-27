from .base import SimpleService


class CtdbService(SimpleService):

    name = 'ctdb'
    systemd_unit = 'ctdb'
    etc = ['ctdb']

    async def before_start(self):
        # we need to make sure the private/public
        # ip files for ctdb are symlinked to the
        # ctdb shared volume (if appropriate)
        if (await self.middleware.call('ctdb.setup.init'))['logit']:
            self.middleware.logger.error('ctdb config setup failed, check logs')

    async def after_start(self):
        await self.middleware.call('ctdb.event.scripts.init')
        await self.middleware.call('ctdb.setup.public_ip_file')
        await self.middleware.call('smb.reset_smb_ha_mode')
        await self.middleware.call('etc.generate', 'smb')

    async def after_stop(self):
        await self.middleware.call('smb.reset_smb_ha_mode')
        await self.middleware.call('etc.generate', 'smb')
        await self.middleware.call('tdb.close_cluster_handles')
