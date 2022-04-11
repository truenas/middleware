from .base import SimpleService


class CIFSService(SimpleService):
    name = "cifs"
    reloadable = True

    etc = ["smb", "smb_share"]

    systemd_unit = "smbd"

    async def start(self):
        is_clustered = await self.middleware.call("smb.getparm", "clustering", "global")
        if is_clustered:
            cluster_healthy = await self.middleware.call("ctdb.general.healthy")
            if not cluster_healthy:
                self.middleware.logger.warning("Cluster is unhealthy. Refusing to start SMB service.")
                return

        await self._systemd_unit("smbd", "start")

    async def stop(self):
        await self._systemd_unit("smbd", "stop")

    async def before_reload(self):
        await self.middleware.call("sharing.smb.sync_registry")
