from middlewared.utils import run

from .base import SimpleService


class CIFSService(SimpleService):
    name = "cifs"
    reloadable = True
    may_run_on_standby = False

    etc = ["smb"]

    systemd_unit = "smbd"

    async def start(self):
        await self._systemd_unit("smbd", "start")

    async def after_start(self):
        # We reconfigure discovery (add SMB service, possibly also ADISK)
        await (await self.middleware.call('service.control', 'RELOAD', 'discovery')).wait(raise_error=True)
        await self.call2(self.s.truesearch.configure)

    async def stop(self):
        await self._systemd_unit("smbd", "stop")

    async def after_stop(self):
        # reconfigure discovery (remove SMB service, possibly also ADISK)
        await (await self.middleware.call('service.control', 'RELOAD', 'discovery')).wait(raise_error=True)
        await self.call2(self.s.truesearch.configure)

    async def reload(self):
        await run(["smbcontrol", "smbd", "reload-config"], check=False)
