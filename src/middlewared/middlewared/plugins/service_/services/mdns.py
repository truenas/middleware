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

        return await super().start()

    async def reload(self):
        announce = (await self.middleware.call("network.configuration.config"))["service_announcement"]
        if not announce["mdns"]:
            return

        return await super().reload()
