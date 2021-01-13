from .base import SimpleService


class GlusterdService(SimpleService):

    name = 'glusterd'
    systemd_unit = 'glusterd'

    restartable = True

    async def after_start(self):
        # the glustereventsd daemon is started via the
        # ctdb.shared.volume.mount method. See comment there
        # to know why we do this.
        await (
            await self.middleware.call('ctdb.shared.volume.mount')
        ).wait(raise_error=True)

    async def after_restart(self):
        # bounce the glustereventsd service
        await self.middleware.call('service.restart', 'glustereventsd')

    async def before_stop(self):
        await (
            await self.middleware.call('ctdb.shared.volume.umount')
        ).wait(raise_error=True)

    async def after_stop(self):
        await self.middleware.call('service.stop', 'glustereventsd')
