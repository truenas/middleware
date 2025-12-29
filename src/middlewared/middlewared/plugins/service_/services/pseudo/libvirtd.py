from middlewared.plugins.service_.services.base import SimpleService


class LibvirtdService(SimpleService):
    name = "libvirtd"
    systemd_unit = "libvirtd"
    etc = ["libvirt"]
    may_run_on_standby = False

    async def after_start(self):
        job = await self.middleware.call(
            "service.control", "START", "libvirt-guests", {"ha_propagate": False}
        )
        await job.wait(raise_error=True)

    async def before_stop(self):
        job = await self.middleware.call("service.control", "STOP", "libvirt-guests")
        await job.wait(raise_error=True)

    async def after_stop(self):
        for service in ('virtlogd.service', 'virtlogd.socket'):
            await self._systemd_unit(service, 'stop')


class LibvirtGuestService(SimpleService):
    name = "libvirt-guests"
    systemd_unit = "libvirt-guests"
    systemd_async_start = True
    etc = ["libvirt_guests"]
    may_run_on_standby = False
