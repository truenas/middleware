import asyncio

from .base import SimpleService


class RsyncService(SimpleService):
    name = "rsync"

    etc = ["rsync"]

    freebsd_rc = "rsyncd"
    freebsd_pidfile = "/var/run/rsyncd.pid"
    freebsd_procname = "rsync"

    systemd_unit = "rsync"

    async def after_stop(self):
        asyncio.ensure_future(await self.middleware.call("rsyncmod.remove_alerts_for_unlocked_datasets"))
