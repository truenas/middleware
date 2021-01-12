from middlewared.plugins.service_.services.base import SimpleService, ServiceState


class LibvirtdService(SimpleService):
    name = "libvirtd"

    freebsd_rc = "libvirtd"

    systemd_unit = "libvirtd"

    etc = ["libvirt"]

    async def _get_state_freebsd(self):
        return ServiceState(
            (await self._freebsd_service("libvirtd", "status")).returncode == 0,
            [],
        )
