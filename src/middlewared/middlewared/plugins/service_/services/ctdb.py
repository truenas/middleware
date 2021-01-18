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
