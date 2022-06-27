from .base import SimpleService


class IdmapService(SimpleService):
    name = "idmap"
    reloadable = True
    restartable = True

    systemd_unit = "winbind"

    async def healthy(self):
        is_clustered = await self.middleware.call("smb.getparm", "clustering", "global")
        if is_clustered:
            cluster_healthy = await self.middleware.call("ctdb.general.healthy")
            if not cluster_healthy:
                self.middleware.logger.warning("Cluster is unhealthy. Refusing to start SMB service.")
                return False

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
