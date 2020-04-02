from middlewared.utils import osc

from middlewared.plugins.service_.services.base import ServiceInterface, ServiceState
from middlewared.plugins.service_.services.base_freebsd import freebsd_service
from middlewared.plugins.service_.services.base_linux import systemd_unit


class PseudoServiceBase(ServiceInterface):
    plugin = NotImplemented

    async def get_state(self):
        return ServiceState(
            await self.middleware.call(f"{self.plugin}.started"),
            [],
        )

    async def start(self):
        await self.middleware.call(f"{self.plugin}.start")

    async def stop(self):
        await self.middleware.call(f"{self.plugin}.stop")


class ActiveDirectoryService(PseudoServiceBase):
    name = "activedirectory"

    reloadable = True
    restartable = True

    plugin = "activedirectory"

    async def restart(self):
        await self.middleware.call("kerberos.stop")
        await self.middleware.call("activedirectory.start")

    async def reload(self):
        if osc.IS_FREEBSD:
            await freebsd_service("winbindd", "quietreload")
        if osc.IS_LINUX:
            await systemd_unit("winbind", "restart")


class LdapService(PseudoServiceBase):
    name = "ldap"

    plugin = "ldap"


class NisService(PseudoServiceBase):
    name = "nis"

    plugin = "nis"
