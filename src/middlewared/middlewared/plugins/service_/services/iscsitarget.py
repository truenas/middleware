from middlewared.utils import run

from .base import SimpleService


class ISCSITargetService(SimpleService):
    name = "iscsitarget"
    reloadable = True
    systemd_async_start = True

    etc = ["scst", "scst_targets"]

    systemd_unit = "scst"

    async def before_start(self):
        await self.middleware.call("iscsi.alua.before_start")

    async def after_start(self):
        await self.middleware.call("iscsi.host.injection.start")
        await self.middleware.call("iscsi.alua.after_start")

    async def before_stop(self):
        await self.middleware.call("iscsi.alua.before_stop")
        await self.middleware.call("iscsi.host.injection.stop")

    async def reload(self):
        return (await run(
            ["scstadmin", "-noprompt", "-force", "-config", "/etc/scst.conf"], check=False
        )).returncode == 0
