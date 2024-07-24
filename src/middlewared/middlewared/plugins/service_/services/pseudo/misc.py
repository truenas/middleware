from pystemd.systemd1 import Unit

from middlewared.plugins.service_.services.base import SimpleService, systemd_unit
from middlewared.plugins.service_.services.base_interface import ServiceInterface
from middlewared.plugins.service_.services.base_state import ServiceState


class PseudoServiceBase(ServiceInterface):
    async def get_state(self):
        return ServiceState(True, [])


class CronService(PseudoServiceBase):
    name = "cron"

    etc = ["cron"]
    restartable = True

    async def restart(self):
        pass


class KmipService(PseudoServiceBase):
    name = "kmip"

    async def start(self):
        await self.middleware.call("service.start", "ssl")
        await self.middleware.call("etc.generate", "kmip")

    async def get_state(self):
        return ServiceState(
            (await self.middleware.call('kmip.config'))['enabled'],
            [],
        )


class IncusService(SimpleService):
    name = "incus"

    systemd_unit = "incus"

    async def stop(self):
        await self._unit_action("Stop")
        # incus.socket needs to be stopped in addition to the service
        unit = Unit("incus.socket")
        unit.load()
        await self._unit_action("Stop", unit=unit)


class LoaderService(PseudoServiceBase):
    name = "loader"

    etc = ["loader"]
    reloadable = True

    async def reload(self):
        pass


class HostnameService(PseudoServiceBase):
    name = "hostname"

    reloadable = True

    async def reload(self):
        await self.middleware.call("etc.generate", "hostname")
        await self.middleware.call("service.restart", "mdns")


class HttpService(PseudoServiceBase):
    name = "http"

    etc = ["nginx"]
    restartable = True
    reloadable = True

    async def restart(self):
        await self.middleware.call("system.general.update_ui_allowlist")
        await systemd_unit("nginx", "restart")

    async def reload(self):
        await self.middleware.call("system.general.update_ui_allowlist")
        await systemd_unit("nginx", "reload")


class NetworkService(PseudoServiceBase):
    name = "network"

    async def start(self):
        await self.middleware.call("interface.sync")
        await self.middleware.call("route.sync")


class NetworkGeneralService(PseudoServiceBase):
    name = "networkgeneral"

    reloadable = True

    async def reload(self):
        await self.middleware.call("service.reload", "resolvconf")
        await self.middleware.call("service.restart", "routing")


class NfsMountdService(PseudoServiceBase):
    '''
    Used in HA mode to stop nfs-mountd on the standby node
    '''
    name = "mountd"

    async def stop(self):
        await systemd_unit("nfs-mountd", "stop")


class NtpdService(SimpleService):
    name = "ntpd"

    etc = ["ntpd"]
    restartable = True

    systemd_unit = "chronyd"


class OpenVmToolsService(SimpleService):
    name = "open-vm-tools"

    systemd_unit = "open-vm-tools"


class PowerdService(SimpleService):
    name = "powerd"

    etc = ["rc"]

    # FIXME: Linux


class RcService(PseudoServiceBase):
    name = "rc"

    etc = ["rc"]
    reloadable = True

    async def reload(self):
        pass


class ResolvConfService(PseudoServiceBase):
    name = "resolvconf"

    reloadable = True

    async def reload(self):
        await self.middleware.call("service.reload", "hostname")
        await self.middleware.call("dns.sync")


class RoutingService(SimpleService):
    name = "routing"

    etc = ["rc"]

    restartable = True

    async def get_state(self):
        return ServiceState(True, [])

    async def restart(self):
        await self.middleware.call("staticroute.sync")


class SslService(PseudoServiceBase):
    name = "ssl"

    etc = ["ssl"]

    async def start(self):
        pass


class SyslogdService(SimpleService):
    name = "syslogd"

    etc = ["syslogd"]
    restartable = True
    reloadable = True

    systemd_unit = "syslog-ng"


class SystemService(PseudoServiceBase):
    name = "system"

    restartable = True

    async def stop(self):
        self.middleware.create_task(self.middleware.call("system.shutdown", {"delay": 3}))

    async def restart(self):
        self.middleware.create_task(self.middleware.call("system.reboot", {"delay": 3}))


class TimeservicesService(PseudoServiceBase):
    name = "timeservices"

    etc = ["localtime"]
    reloadable = True

    async def reload(self):
        await self.middleware.call("service.restart", "ntpd")

        settings = await self.middleware.call("datastore.config", "system.settings")
        await self.middleware.call("core.environ_update", {"TZ": settings["stg_timezone"]})


class UserService(PseudoServiceBase):
    name = "user"

    etc = ["user"]
    reloadable = True

    async def reload(self):
        pass
