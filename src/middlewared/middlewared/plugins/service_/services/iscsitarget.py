import contextlib

from middlewared.utils import osc

if osc.IS_FREEBSD:
    import sysctl

from .base import SimpleService


class ISCSITargetService(SimpleService):
    name = "iscsitarget"
    reloadable = True

    etc = ["ctld"]

    freebsd_rc = "ctld"
    freebsd_pidfile = "/var/run/ctld.pid"

    async def before_stop(self):
        if osc.IS_FREEBSD:
            with contextlib.suppress(IndexError):
                sysctl.filter("kern.cam.ctl.ha_peer")[0].value = ""
