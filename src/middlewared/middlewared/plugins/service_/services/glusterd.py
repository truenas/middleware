from .base import SimpleService
from middlewared.plugins.cluster_linux.utils import CTDBConfig

CTDB_VOL = CTDBConfig.CTDB_VOL_NAME.value


class GlusterdService(SimpleService):

    name = 'glusterd'
    systemd_unit = 'glusterd'

    restartable = True

    async def after_start(self):
        mount_job = await self.middleware.call('gluster.fuse.mount', {'all': True})
        await mount_job.wait()
        if await self.middleware.call('gluster.fuse.is_mounted', {'name': CTDB_VOL}):
            await self.middleware.call('service.start', 'ctdb')

    async def after_restart(self):
        await self.middleware.call('service.restart', 'glustereventsd')

    async def before_stop(self):
        await self.middleware.call('service.stop', 'ctdb')
        umount_job = await self.middleware.call('gluster.fuse.umount', {'all': True})
        await umount_job.wait()

    async def after_stop(self):
        await self.middleware.call('service.stop', 'glustereventsd')
