from middlewared.utils import osc, run

from .base import SimpleService


class ISCSITargetService(SimpleService):
    name = "iscsitarget"
    reloadable = True

    etc = ["ctld", "scst"]

    freebsd_rc = "ctld"
    freebsd_pidfile = "/var/run/ctld.pid"

    systemd_unit = "scst"

    async def after_start(self):
        await self.middleware.call("iscsi.host.injection.start")

    async def before_stop(self):
        await self.middleware.call("iscsi.host.injection.stop")

    async def reload(self):
        if osc.IS_LINUX:
            return (await run(
                ["scstadmin", "-noprompt", "-force", "-config", "/etc/scst.conf"], check=False
            )).returncode == 0
        else:
            return await self._reload_freebsd()
