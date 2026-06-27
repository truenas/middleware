from middlewared.utils import run

from .base import SimpleService


class CIFSService(SimpleService):
    name = "cifs"
    reloadable = True
    may_run_on_standby = False

    etc = ["smb"]

    systemd_unit = "smbd"

    async def start(self) -> None:
        await self._systemd_unit("smbd", "start")

    async def after_start(self) -> None:
        # We reconfigure discovery (add SMB service, possibly also ADISK)
        await (await self.middleware.call('service.control', 'RELOAD', 'discovery')).wait(raise_error=True)
        await self.call2(self.s.truesearch.configure)

    async def stop(self) -> None:
        await self._systemd_unit("smbd", "stop")

    async def after_stop(self) -> None:
        # reconfigure discovery (remove SMB service, possibly also ADISK)
        await (await self.middleware.call('service.control', 'RELOAD', 'discovery')).wait(raise_error=True)
        await self.call2(self.s.truesearch.configure)

    async def reload(self) -> None:
        await run(["smbcontrol", "smbd", "reload-config"], check=False)
