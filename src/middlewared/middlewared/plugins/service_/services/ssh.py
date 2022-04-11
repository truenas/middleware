from .base import SimpleService


class SSHService(SimpleService):
    name = "ssh"
    reloadable = True

    etc = ["ssh"]

    systemd_unit = "ssh"

    async def after_start(self):
        await self.middleware.call("ssh.save_keys")

    async def after_reload(self):
        await self.middleware.call("ssh.save_keys")
