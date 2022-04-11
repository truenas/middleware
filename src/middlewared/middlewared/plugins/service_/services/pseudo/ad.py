from middlewared.plugins.service_.services.base import ServiceInterface, ServiceState
from middlewared.plugins.service_.services.base import systemd_unit


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
        await systemd_unit("winbind", "restart")


class LdapService(PseudoServiceBase):
    name = "ldap"

    plugin = "ldap"


class NisService(PseudoServiceBase):
    name = "nis"

    plugin = "nis"
