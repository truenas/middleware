from .base import SimpleService


class NetBIOSService(SimpleService):
    name = "nmbd"

    systemd_unit = "nmbd"

    async def identify(self, procname):
        return procname == "nmbd"
