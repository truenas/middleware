import contextlib
import platform

if platform.system() == "FreeBSD":
    import sysctl

from .base import SimpleService


class ISCSITargetService(SimpleService):
    name = "iscsitarget"
    reloadable = True

    etc = ["ctld"]

    freebsd_rc = "ctld"
    freebsd_pidfile = "/var/run/ctld.pid"

    async def before_stop(self):
        if platform.system() == "FreeBSD":
            with contextlib.suppress(IndexError):
                sysctl.filter("kern.cam.ctl.ha_peer")[0].value = ""
