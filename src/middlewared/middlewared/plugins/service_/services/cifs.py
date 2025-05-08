import errno

from .base import SimpleService
from middlewared.service_exception import CallError


class CIFSService(SimpleService):
    name = "cifs"
    reloadable = True

    etc = ["smb"]

    systemd_unit = "smbd"

    async def start(self):
        if not await self.middleware.call("smb.configure_wait"):
            return

        await self._systemd_unit("smbd", "start")

    async def after_start(self):
        # We reconfigure mdns (add SMB service, possibly also ADISK)
        await self.middleware.call('service.reload', 'mdns')

    async def stop(self):
        await self._systemd_unit("smbd", "stop")

    async def after_stop(self):
        # reconfigure mdns (remove SMB service, possibly also ADISK)
        await self.middleware.call('service.reload', 'mdns')
