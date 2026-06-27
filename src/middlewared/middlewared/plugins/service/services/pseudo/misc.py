import asyncio

from truenas_connect_utils.status import Status

from middlewared.plugins.service.services.base import SimpleService
from middlewared.plugins.service.services.base_interface import ServiceInterface
from middlewared.plugins.service.services.base_state import ServiceState
from middlewared.plugins.service.services.dbus_router import system_dbus
from middlewared.utils.timezone_choices import effective_timezone


class PseudoServiceBase(ServiceInterface):
    async def get_state(self) -> ServiceState:
        return ServiceState(True, [])


class CronService(PseudoServiceBase):
    name = "cron"

    etc = ["cron"]
    restartable = True

    async def restart(self) -> None:
        pass


class KmipService(PseudoServiceBase):
    name = "kmip"

    async def start(self) -> None:
        await (await self.call2(self.s.service.control, "START", "ssl")).wait(raise_error=True)
        await self.middleware.call("etc.generate", "kmip")

    async def get_state(self) -> ServiceState:
        return ServiceState(
            (await self.middleware.call2(self.middleware.services.kmip.config)).enabled,
            [],
        )


class LoaderService(PseudoServiceBase):
    name = "loader"

    etc = ["loader"]
    reloadable = True

    async def reload(self) -> None:
        pass


class HostnameService(PseudoServiceBase):
    name = "hostname"

    reloadable = True

    async def reload(self) -> None:
        await self.middleware.call("etc.generate", "hostname")
        await (await self.call2(self.s.service.control, "RESTART", "discovery")).wait(raise_error=True)


class HttpService(PseudoServiceBase):
    name = "http"

    etc = ["nginx"]
    restartable = True
    reloadable = True

    async def _register_new_port(self) -> None:
        """Create a task that sends the new HTTPS port to TNC if configured."""
        port_changed, new_port = await self.middleware.call("system.general.https_port_changed")
        if port_changed and (await self.call2(self.s.tn_connect.config)).status == Status.CONFIGURED.name:
            self.middleware.create_task(self._register_port_with_retry(new_port))

    async def _register_port_with_retry(self, new_port: int) -> None:
        """Register port with TNC with retry logic."""
        for attempt in range(3):
            try:
                await self.call2(self.s.tn_connect.hostname.register_system_config, new_port)
                return
            except Exception as e:
                if attempt == 2:  # Last attempt
                    self.middleware.logger.error("Failed to register port with TrueNAS Connect after 3 attempts: %s", e)
                else:
                    await asyncio.sleep(5)

    async def restart(self) -> None:
        await self.middleware.call("system.general.update_ui_allowlist")
        await system_dbus.systemd_unit("nginx", "restart")

    async def after_restart(self) -> None:
        await self._register_new_port()

    async def reload(self) -> None:
        await self.middleware.call("system.general.update_ui_allowlist")
        await system_dbus.systemd_unit("nginx", "reload")

    async def after_reload(self) -> None:
        await self._register_new_port()


class NetworkService(PseudoServiceBase):
    name = "network"

    async def start(self) -> None:
        await self.middleware.call("interface.sync")
        await self.call2(self.s.route.sync)


class NetworkGeneralService(PseudoServiceBase):
    name = "networkgeneral"

    reloadable = True

    async def reload(self) -> None:
        await (await self.call2(self.s.service.control, "RELOAD", "resolvconf")).wait(raise_error=True)
        await (await self.call2(self.s.service.control, "RESTART", "routing")).wait(raise_error=True)


class NfsMountdService(SimpleService):
    """
    Used in HA mode to stop nfs-mountd on the standby node
    """
    name = "mountd"
    may_run_on_standby = False
    systemd_unit = "nfs-mountd"


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

    async def reload(self) -> None:
        pass


class ResolvConfService(PseudoServiceBase):
    name = "resolvconf"

    reloadable = True

    async def reload(self) -> None:
        await (await self.call2(self.s.service.control, "RELOAD", "hostname")).wait(raise_error=True)
        await self.middleware.call("dns.sync")


class RoutingService(SimpleService):
    name = "routing"

    etc = ["rc"]

    restartable = True

    async def get_state(self) -> ServiceState:
        return ServiceState(True, [])

    async def restart(self) -> None:
        await self.call2(self.s.staticroute.sync)


class SslService(PseudoServiceBase):
    name = "ssl"

    etc = ["ssl"]

    async def start(self) -> None:
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

    async def reload(self) -> None:
        await (await self.call2(self.s.service.control, "RESTART", "ntpd")).wait(raise_error=True)

        settings = await self.middleware.call("datastore.config", "system.settings")
        await self.middleware.call(
            "core.environ_update", {"TZ": effective_timezone(settings["stg_timezone"])}
        )


class UserService(PseudoServiceBase):
    name = "user"

    etc = ["user"]
    reloadable = True

    async def reload(self) -> None:
        pass


class NVMETargetService(PseudoServiceBase):
    name = "nvmet"
    etc = ["nvmet"]
    reloadable = True

    systemd_unit: str

    async def start(self) -> None:
        await self.middleware.call('nvmet.global.start')

    async def stop(self) -> None:
        await self.middleware.call('nvmet.global.stop')

    async def reload(self) -> None:
        # etc.generate is called before we get here
        pass

    async def become_active(self) -> None:
        if await self.middleware.call('nvmet.global.running'):
            # If necessary we can optimize to *just* poke the
            # 1. port ANA group state
            # 2. namespace enabled
            await self.middleware.call('etc.generate', self.name)
        else:
            await self.start()

    async def get_state(self) -> ServiceState:
        return ServiceState(
            (await self.middleware.call('nvmet.global.running')),
            [],
        )

    async def failure_logs(self, failed_units: dict[str, tuple[str, int]] | None = None) -> str:
        if (await self.middleware.call('nvmet.global.config'))['kernel']:
            return ""
        else:
            service_object = await self.call2(self.s.service.object, "nvmf")
            return await service_object.failure_logs()


class NVMfService(SimpleService):
    name = "nvmf"
    reloadable = True
    etc = ["nvmet"]
    systemd_unit = "ix-nvmf"


class RpcGssService(SimpleService):
    """Start auth-rpcgss-module service to
       enable gssproxy usage"""
    name = "auth-rpcgss-module"

    systemd_unit = "auth-rpcgss-module"
