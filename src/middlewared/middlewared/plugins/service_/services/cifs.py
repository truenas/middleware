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
        # We reconfigure mdns (add SMB service, possibly also ADISK)
        await (await self.middleware.call('service.control', 'RELOAD', 'mdns')).wait(raise_error=True)
        await self.middleware.call('truesearch.configure')

    async def stop(self):
        await self._systemd_unit("smbd", "stop")

    async def after_stop(self):
        # reconfigure mdns (remove SMB service, possibly also ADISK)
        await (await self.middleware.call('service.control', 'RELOAD', 'mdns')).wait(raise_error=True)
        await self.middleware.call('truesearch.configure')
