from .base import SimpleService


class WebShareService(SimpleService):
    name = "webshare"
    reloadable = True
    etc = ["webshare"]

    systemd_unit = "truenas-webshare-auth"

    async def before_start(self):
        # Configuration validation is handled by the webshare plugin
        await self.middleware.call("webshare.before_start")

    async def check_configuration(self):
        await self.middleware.call("webshare.check_configuration")
