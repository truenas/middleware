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
        await (await self.middleware.call("service.control", "START", "ssl")).wait(raise_error=True)
        await self.middleware.call("etc.generate", "kmip")

    async def get_state(self):
        return ServiceState(
            (await self.middleware.call('kmip.config'))['enabled'],
            [],
        )


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
        await (await self.middleware.call("service.control", "RESTART", "mdns")).wait(raise_error=True)


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
        await (await self.middleware.call("service.control", "RELOAD", "resolvconf")).wait(raise_error=True)
        await (await self.middleware.call("service.control", "RESTART", "routing")).wait(raise_error=True)


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
        await (await self.middleware.call("service.control", "RELOAD", "hostname")).wait(raise_error=True)
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


class TimeservicesService(PseudoServiceBase):
    name = "timeservices"

    etc = ["localtime"]
    reloadable = True

    async def reload(self):
        await (await self.middleware.call("service.control", "RESTART", "ntpd")).wait(raise_error=True)

        settings = await self.middleware.call("datastore.config", "system.settings")
        await self.middleware.call("core.environ_update", {"TZ": settings["stg_timezone"]})


class UserService(PseudoServiceBase):
    name = "user"

    etc = ["user"]
    reloadable = True

    async def reload(self):
        pass


class NVMETargetService(PseudoServiceBase):
    name = "nvmet"
    systemd_unit = NotImplemented

    etc = ["nvmet"]
    reloadable = True

    async def start(self):
        await self.middleware.call('nvmet.global.start')

    async def stop(self):
        await self.middleware.call('nvmet.global.stop')

    async def reload(self):
        # etc.generate is called before we get here
        pass

    async def become_active(self):
        if await self.middleware.call('nvmet.global.running'):
            # If necessary we can optimize to *just* poke the
            # 1. port ANA group state
            # 2. namespace enabled
            await self.middleware.call('etc.generate', self.name)
        else:
            await self.start()

    async def get_state(self):
        return ServiceState(
            (await self.middleware.call('nvmet.global.running')),
            [],
        )

    async def failure_logs(self):
        if (await self.middleware.call('nvmet.global.config'))['kernel']:
            return None
        else:
            service_object = await self.middleware.call('service.object', "nvmf")
            return await service_object.failure_logs()


class NVMfService(SimpleService):
    name = "nvmf"
    reloadable = True
    etc = ["nvmet"]
    systemd_unit = "ix-nvmf"
