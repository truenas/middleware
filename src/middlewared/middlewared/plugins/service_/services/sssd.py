from .base import SimpleService


class SSSDService(SimpleService):
    name = "sssd"

    systemd_unit = "sssd"

    async def before_start(self):
        await self.middleware.call('ldap.create_sssd_dirs')
