from .base import SimpleService


class SSHService(SimpleService):
    name = "ssh"
    reloadable = True

    etc = ["ssh"]

    freebsd_rc = "openssh"
    freebsd_procname = "sshd"
    freebsd_pidfile = "/var/run/sshd.pid"

    systemd_unit = "ssh"

    async def before_start(self):
        await self.middleware.call("service.reload", "mdns")

    async def after_start(self):
        await self.middleware.call("ssh.save_keys")

    async def before_reload(self):
        await self.middleware.call("service.reload", "mdns")

    async def after_reload(self):
        await self.middleware.call("ssh.save_keys")
