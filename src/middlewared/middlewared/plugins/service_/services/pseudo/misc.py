import asyncio

from middlewared.utils import osc, run

from middlewared.plugins.service_.services.base import ServiceState, ServiceInterface, SimpleService
from middlewared.plugins.service_.services.base_freebsd import freebsd_service


class PseudoServiceBase(ServiceInterface):
    async def get_state(self):
        return ServiceState(True, [])


class CronService(PseudoServiceBase):
    name = "cron"

    etc = ["cron"]
    restartable = True

    async def restart(self):
        pass


class DiskService(PseudoServiceBase):
    name = "disk"

    etc = ["fstab"]
    restartable = True
    reloadable = True

    async def restart(self):
        await self.reload()

    async def reload(self):
        if osc.IS_FREEBSD:
            await freebsd_service("mountlate", "start")

        asyncio.ensure_future(self.middleware.call("service.restart", "collectd"))


class FailoverService(PseudoServiceBase):
    name = "failover"

    etc = ["failover"]
    restartable = True

    async def restart(self):
        if osc.IS_FREEBSD:
            await freebsd_service("devd", "restart")


class KmipService(PseudoServiceBase):
    name = "kmip"

    async def start(self):
        await self.middleware.call("service.start", "ssl")
        await self.middleware.call("etc.generate", "kmip")


class LoaderService(PseudoServiceBase):
    name = "loader"

    etc = ["loader"]
    reloadable = True

    async def reload(self):
        pass


class MOTDService(PseudoServiceBase):
    name = "motd"

    etc = ["motd"]

    async def start(self):
        if osc.IS_FREEBSD:
            await freebsd_service("motd", "start")


class HostnameService(PseudoServiceBase):
    name = "hostname"

    reloadable = True

    async def reload(self):
        await run(["hostname", ""])
        await self.middleware.call("etc.generate", "hostname")
        await self.middleware.call("etc.generate", "rc")
        if osc.IS_FREEBSD:
            await freebsd_service("hostname", "start")
        await self.middleware.call("service.restart", "mdns")
        await self.middleware.call("service.restart", "collectd")


class HttpService(PseudoServiceBase):
    name = "http"

    etc = ["nginx"]
    restartable = True
    reloadable = True

    async def restart(self):
        await self.middleware.call("service.reload", "mdns")
        if osc.IS_FREEBSD:
            await freebsd_service("nginx", "restart")

    async def reload(self):
        await self.middleware.call("service.reload", "mdns")
        if osc.IS_FREEBSD:
            await freebsd_service("nginx", "reload")


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
        if osc.IS_FREEBSD:
            await freebsd_service("routing", "restart")


class NtpdService(SimpleService):
    name = "ntpd"

    etc = ["ntpd"]
    restartable = True

    freebsd_rc = "ntpd"


class PowerdService(SimpleService):
    name = "powerd"

    etc = ["rc"]

    freebsd_rc = "powerd"


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

    freebsd_rc = "routing"


class SslService(PseudoServiceBase):
    name = "ssl"

    etc = ["ssl"]

    async def start(self):
        pass


class SysconsService(SimpleService):
    name = "syscons"

    etc = ["rc"]
    restartable = True

    freebsd_rc = "syscons"


class SysctlService(PseudoServiceBase):
    name = "sysctl"

    etc = ["sysctl"]
    reloadable = True

    async def reload(self):
        pass


class SyslogdService(SimpleService):
    name = "syslogd"

    etc = ["syslogd"]
    restartable = True
    reloadable = True

    freebsd_rc = "syslog-ng"


class SystemService(PseudoServiceBase):
    name = "system"

    restartable = True

    async def stop(self):
        asyncio.ensure_future(self.middleware.call("system.shutdown", {"delay": 3}))

    async def restart(self):
        asyncio.ensure_future(self.middleware.call("system.reboot", {"delay": 3}))


class SystemDatasetsService(PseudoServiceBase):
    name = "system_datasets"

    restartable = True

    async def restart(self):
        systemdataset = await self.middleware.call("systemdataset.setup")
        if not systemdataset:
            return None

        if systemdataset["syslog"]:
            await self.middleware.call("service.restart", "syslogd")

        await self.middleware.call("service.restart", "cifs")

        # Restarting rrdcached can take a long time. There is no
        # benefit in waiting for it, since even if it fails it will not
        # tell the user anything useful.
        # Restarting rrdcached will make sure that we start/restart collectd as well
        asyncio.ensure_future(self.middleware.call("service.restart", "rrdcached"))


class TimeservicesService(PseudoServiceBase):
    name = "timeservices"

    etc = ["localtime"]
    reloadable = True

    async def reload(self):
        await self.middleware.call("service.restart", "ntpd")

        settings = await self.middleware.call("datastore.config", "system.settings")
        await self.middleware.call("core.environ_update", {"TZ": settings["stg_timezone"]})


class TtysService(PseudoServiceBase):
    name = "ttys"

    etc = ["ttys"]

    async def start(self):
        pass


class UserService(PseudoServiceBase):
    name = "user"

    etc = ["user", "aliases", "sudoers"]
    reloadable = True

    async def reload(self):
        await self.middleware.call("service.reload", "cifs")
