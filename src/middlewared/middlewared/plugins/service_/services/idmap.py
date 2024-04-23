from .base import SimpleService


class IdmapService(SimpleService):
    name = "idmap"
    reloadable = True
    restartable = True
    default_ha_propagate = False

    systemd_unit = "winbind"

    async def healthy(self):
        return await self.middleware.call("smb.configure_wait")

    async def start(self):
        if not await self.healthy():
            return

        await self._systemd_unit("winbind", "start")

    async def restart(self):
        if not await self.healthy():
            return

        return await self._systemd_unit("winbind", "restart")

    async def reload(self):
        if not await self.healthy():
            return

        return await self._systemd_unit("winbind", "reload")
