from .base import SimpleService


class SSHService(SimpleService):
    name = "ssh"
    reloadable = True

    etc = ["ssh"]

    systemd_unit = "ssh"

    async def after_start(self) -> None:
        await self.middleware.call2(self.middleware.services.ssh.save_keys)

    async def after_reload(self) -> None:
        await self.middleware.call2(self.middleware.services.ssh.save_keys)
