import errno

from .base import SimpleService
from middlewared.service_exception import CallError


class CIFSService(SimpleService):
    name = "cifs"
    reloadable = True

    etc = ["smb"]

    systemd_unit = "smbd"

    async def check_configuration(self):
        is_clustered = await self.middleware.call("smb.getparm", "clustering", "global")
        if is_clustered and not (await self.middleware.call("ctdb.general.healthy")):
            raise CallError("Cluster is unhealthy. Refusing to start SMB service.", errno.EINVAL)

    async def start(self):
        if not await self.middleware.call("smb.configure_wait"):
            return

        await self._systemd_unit("smbd", "start")

    async def stop(self):
        await self._systemd_unit("smbd", "stop")

    async def before_reload(self):
        await self.middleware.call("sharing.smb.sync_registry")
