from middlewared.utils import osc, run

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
            cp = await run(["sysctl", "kern.cam.ctl.ha_peer=''"], check=False)
            if cp.returncode and "unknown oid" not in cp.stderr.decode().lower():
                self.middleware.logger.error(
                    "Failed to set sysctl kern.cam.ctl.ha_peer : %s", cp.stderr.decode()
                )

    async def reload(self):
        if osc.IS_LINUX:
            return (await run(
                ["scstadmin", "-noprompt", "-force", "-config", "/etc/scst.conf"], check=False
            )).returncode == 0
        else:
            return await self._reload_freebsd()
