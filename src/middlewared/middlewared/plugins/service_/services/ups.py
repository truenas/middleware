from .base import SimpleService


class UPSService(SimpleService):
    name = "ups"
    etc = ["ups"]
    systemd_unit = "nut-monitor"

    async def systemd_extra_units(self):
        if (await self.middleware.call("ups.config"))["mode"] == "MASTER":
            return ["nut-driver-enumerator", "nut-server", "nut.target"]
        else:
            return ["nut.target"]

    async def before_start(self):
        await self.middleware.call("ups.dismiss_alerts")

    async def start(self):
        if (await self.middleware.call("ups.config"))["mode"] == "MASTER":
            await self._systemd_unit("nut-server", "start")
            await self._systemd_unit("nut-driver-enumerator", "start")
        await self._unit_action("Start")

    async def after_start(self):
        # Reconfigure mdns (add nut service)
        await self.middleware.call('service.reload', 'mdns', {'ha_propagate': False})

    async def before_stop(self):
        await self.middleware.call("ups.dismiss_alerts")

    async def stop(self):
        await self._unit_action("Stop")
        await self._systemd_unit("nut-driver-enumerator", "stop")
        await self._systemd_unit("nut-server", "stop")
        await self._systemd_unit("nut-driver.target", "stop")

    async def after_stop(self):
        # Reconfigure mdns (remove nut service)
        await self.middleware.call('service.reload', 'mdns', {'ha_propagate': False})
