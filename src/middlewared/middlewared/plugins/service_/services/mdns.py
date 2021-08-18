from .base import SimpleService


class MDNSService(SimpleService):
    name = "mdns"
    reloadable = True

    etc = ["mdns"]

    freebsd_rc = "avahi-daemon"
    freebsd_pidfile = "/var/run/avahi-daemon/pid"

    systemd_unit = "avahi-daemon"

    async def start(self):
        announce = (await self.middleware.call("network.configuration.config"))["service_announcement"]
        if not announce["mdns"]:
            return

        return await self._systemd_unit("avahi-daemon", "start")

    async def reload(self):
        announce = (await self.middleware.call("network.configuration.config"))["service_announcement"]
        if not announce["mdns"]:
            return

        state = await self.get_state()
        cmd = "reload" if state.running else "start"
        return await self._systemd_unit("avahi-daemon", cmd)
