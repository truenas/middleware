from middlewared.plugins.service_.services.base import SimpleService


class LibvirtdService(SimpleService):
    name = "libvirtd"
    systemd_unit = "libvirtd"
    etc = ["libvirt"]

    async def after_start(self):
        await (await self.middleware.call("service.control", "START", "libvirt-guests", {"ha_propagate": False})).wait(raise_error=True)

    async def before_stop(self):
        await (await self.middleware.call("service.control", "STOP", "libvirt-guests")).wait(raise_error=True)


class LibvirtGuestService(SimpleService):
    name = "libvirt-guests"
    systemd_unit = "libvirt-guests"
    systemd_async_start = True
    etc = ["libvirt_guests"]
