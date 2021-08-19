from .base import SimpleService


class IdmapService(SimpleService):
    name = "idmap"
    reloadable = True
    restartable = True

    systemd_unit = "winbind"

    async def restart(self):
        return await self._systemd_unit("winbind", "restart")

    async def reload(self):
        return await self._systemd_unit("winbind", "reload")
