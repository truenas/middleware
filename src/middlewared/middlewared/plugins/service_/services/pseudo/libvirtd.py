from middlewared.plugins.service_.services.base import SimpleService


class LibvirtdService(SimpleService):
    name = "libvirtd"
    systemd_unit = "libvirtd"
    etc = ["libvirt"]
    may_run_on_standby = False

    async def after_start(self):
        await self.middleware.call("service.start", "libvirt-guests", {"ha_propagate": False})

    async def before_stop(self):
        await self.middleware.call("service.stop", "libvirt-guests")

    async def after_stop(self):
        for service in ('virtlockd.socket', 'virtlogd.socket', 'virtlockd.service', 'virtlogd.service'):
            await self._systemd_unit(service, 'stop')


class LibvirtGuestService(SimpleService):
    name = "libvirt-guests"
    systemd_unit = "libvirt-guests"
    systemd_async_start = True
    etc = ["libvirt_guests"]
    may_run_on_standby = False
