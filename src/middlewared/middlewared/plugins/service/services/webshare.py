from .base import SimpleService


class WebShareService(SimpleService):
    name = "webshare"

    etc = ["webshare"]
    reloadable = True
    may_run_on_standby = False

    systemd_unit = "truenas-webshare-auth"
    systemd_async_start = True
    systemd_sidecar_units = (
        "truenas-webshare-caddy",
        "truenas-webshare-link",
        "truenas-webshare-link-caddy",
        "truenas-webshare-mcp",
    )

    async def after_start(self) -> None:
        await self.call2(self.s.truesearch.configure)

    async def after_stop(self) -> None:
        await self.call2(self.s.truesearch.configure)
