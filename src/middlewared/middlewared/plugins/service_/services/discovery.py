from .base import SimpleService


class DiscoveryService(SimpleService):
    name = "discovery"
    reloadable = True
    may_run_on_standby = False

    etc = ["discovery"]

    systemd_unit = "truenas-discoveryd"

    async def reload(self):
        announce = (await self.middleware.call("network.configuration.config"))["service_announcement"]
        if not any(announce.get(k) for k in ("mdns", "netbios", "wsd")):
            return

        state = await self.get_state()
        cmd = "reload" if state.running else "start"
        return await self._systemd_unit("truenas-discoveryd", cmd)
