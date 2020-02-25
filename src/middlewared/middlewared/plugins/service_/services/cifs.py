from middlewared.service_exception import CallError

from .base import SimpleService, ServiceState


class CIFSService(SimpleService):
    name = "cifs"
    reloadable = True

    etc = ["smb", "smb_share"]

    freebsd_rc = "smbd"
    freebsd_pidfile = "/var/run/samba4/smbd.pid"

    async def _get_state_freebsd(self):
        return ServiceState(
            (await self._freebsd_service("smbd", "status")).returncode == 0,
            [],
        )

    async def _start_freebsd(self):
        announce = (await self.middleware.call("network.configuration.config"))["service_announcement"]
        await self._freebsd_service("smbd", "start", force=True)
        await self._freebsd_service("winbindd", "start", force=True)
        if announce["netbios"]:
            await self._freebsd_service("nmbd", "start", force=True)
        if announce["wsd"]:
            await self._freebsd_service("wsdd", "start", force=True)

    async def after_start(self):
        await self.middleware.call("service.reload", "mdns")

        try:
            await self.middleware.call("smb.add_admin_group", "", True)
        except Exception as e:
            raise CallError(e)

    async def _stop_freebsd(self):
        await self._freebsd_service("smbd", "stop", force=True)
        await self._freebsd_service("winbindd", "stop", force=True)
        await self._freebsd_service("nmbd", "stop", force=True)
        await self._freebsd_service("wsdd", "stop", force=True)

    async def after_stop(self):
        await self.middleware.call("service.reload", "mdns")

    async def after_reload(self):
        await self.middleware.call("service.reload", "mdns")
