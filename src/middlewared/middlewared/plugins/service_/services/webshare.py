from .base import SimpleService


class WebShareService(SimpleService):
    name = "webshare"

    etc = ["webshare"]
    reloadable = True
    may_run_on_standby = False

    systemd_unit = "truenas-webshare-auth"
    systemd_async_start = True

    async def after_start(self):
        await self.call2(self.s.truesearch.configure)

    async def after_stop(self):
        await self.call2(self.s.truesearch.configure)
