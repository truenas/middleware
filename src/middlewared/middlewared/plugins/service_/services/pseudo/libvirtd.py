from middlewared.plugins.service_.services.base import SimpleService


class LibvirtdService(SimpleService):
    name = "libvirtd"
    systemd_unit = "libvirtd"
    etc = ["libvirt"]

    async def after_start(self):
        await self.middleware.call("service.start", "libvirt-guests")

    async def before_stop(self):
        await self.middleware.call("service.stop", "libvirt-guests")


class LibvirtGuestService(SimpleService):
    name = "libvirt-guests"
    systemd_unit = "libvirt-guests"
    systemd_async_start = True
    etc = ["libvirt_guests"]
