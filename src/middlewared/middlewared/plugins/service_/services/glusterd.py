from .base import SimpleService
from middlewared.plugins.gluster_linux.utils import GlusterConfig

URL = GlusterConfig.LOCAL_EVENTSD_WEBHOOK_URL.value


class GlusterdService(SimpleService):

    name = 'glusterd'
    systemd_unit = 'glusterd'

    restartable = True

    async def after_start(self):
        # glustereventsd needs to be started always
        # since it's responsible for sending
        # events to middlewared to be acted upon
        await self.middleware.call('service.start', 'glustereventsd')
        await self.middleware.call('gluster.eventsd.create', {'url': URL})

    async def after_restart(self):
        # bounce the glustereventsd service
        await self.middleware.call('service.restart', 'glustereventsd')

    async def after_stop(self):
        # no reason to keep this running if glusterd service
        # is stopped
        await self.middleware.call('service.stop', 'glustereventsd')
