import contextlib

from middlewared.utils import osc, run

if osc.IS_FREEBSD:
    import sysctl

from .base import SimpleService


class ISCSITargetService(SimpleService):
    name = "iscsitarget"
    reloadable = True

    etc = ["ctld", "scst"]

    freebsd_rc = "ctld"
    freebsd_pidfile = "/var/run/ctld.pid"

    systemd_unit = "scst"

    async def before_stop(self):
        if osc.IS_FREEBSD:
            with contextlib.suppress(IndexError):
                sysctl.filter("kern.cam.ctl.ha_peer")[0].value = ""

    async def reload(self):
        if osc.IS_LINUX:
            return (await run(
                ["scstadmin", "-noprompt", "-force", "-config", "/etc/scst.conf"], check=False
            )).returncode == 0
        else:
            return await self._reload_freebsd()
