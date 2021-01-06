from .base import SimpleService


class GlusterdService(SimpleService):

    name = 'glusterd'
    systemd_unit = 'glusterd'

    restartable = True

    async def after_start(self):
        # glustereventsd needs to be started always
        # since it's responsible for sending
        # events to middlewared to be acted upon
        await self.middleware.call('service.start', 'glustereventsd')
        await (
            await self.middleware.call('ctdb.shared.volume.mount')
        ).wait(raise_error=True)

    async def after_restart(self):
        # bounce the glustereventsd service
        await self.middleware.call('service.restart', 'glustereventsd')

    async def before_stop(self):
        # ctdb_shared_vol is FUSE mounted locally so umount
        # it before we stop the glusterd service
        await (
            await self.middleware.call('ctdb.shared.volume.umount')
        ).wait(raise_error=True)

    async def after_stop(self):
        # no reason to keep this running if glusterd service
        # is stopped
        await self.middleware.call('service.stop', 'glustereventsd')
