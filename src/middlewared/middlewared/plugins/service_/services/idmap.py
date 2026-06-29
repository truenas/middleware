from .base import SimpleService


class IdmapService(SimpleService):
    name = "idmap"
    reloadable = True
    restartable = True

    systemd_unit = "winbind"

    async def healthy(self) -> bool:
        return await self.middleware.call("smb.is_configured")  # type: ignore[no-any-return]

    async def start(self) -> None:
        if not await self.healthy():
            return

        await self._systemd_unit("winbind", "start")

    async def restart(self) -> None:
        if not await self.healthy():
            return

        await self._systemd_unit("winbind", "restart")

    async def reload(self) -> None:
        if not await self.healthy():
            return

        await self._systemd_unit("winbind", "reload")
