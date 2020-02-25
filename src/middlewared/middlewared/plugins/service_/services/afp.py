import platform

from middlewared.utils import run

from .base import SimpleService


class AFPService(SimpleService):
    name = "afp"
    reloadable = True

    etc = ["afpd"]

    freebsd_rc = "netatalk"

    async def after_start(self):
        await self.middleware.call("service.reload", "mdns")

    async def after_stop(self):
        if platform.system() == "FreeBSD":
            # when netatalk stops if afpd or cnid_metad is stuck
            # they'll get left behind, which can cause issues
            # restarting netatalk.
            await run("pkill", "-9", "afpd", check=False)
            await run("pkill", "-9", "cnid_metad", check=False)

        await self.middleware.call("service.reload", "mdns")

    async def _reload_freebsd(self):
        await run("killall", "-1", "netatalk", check=False)
        await self.middleware.call("service.reload", "mdns")
