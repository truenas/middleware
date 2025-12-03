from .base import SimpleService


class WebShareService(SimpleService):
    name = "webshare"

    etc = ["webshare"]
    reloadable = True

    systemd_unit = "truenas-webshare-auth"
    systemd_async_start = True

    async def after_start(self):
        await self.middleware.call("truesearch.configure")

    async def after_stop(self):
        await self.middleware.call("truesearch.configure")
