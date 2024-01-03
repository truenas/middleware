from middlewared.utils import run

from .base import SimpleService


class ISCSITargetService(SimpleService):
    name = "iscsitarget"
    reloadable = True
    systemd_unit_timeout = 30

    etc = ["scst", "scst_targets"]

    systemd_unit = "scst"

    async def after_start(self):
        await self.middleware.call("iscsi.host.injection.start")

    async def before_stop(self):
        await self.middleware.call("iscsi.host.injection.stop")

    async def reload(self):
        return (await run(
            ["scstadmin", "-noprompt", "-force", "-config", "/etc/scst.conf"], check=False
        )).returncode == 0
