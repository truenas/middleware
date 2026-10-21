from truenas_pylicensed.features import LicenseFeature

from middlewared.service_exception import CallError

from .base import SimpleService


class WebShareService(SimpleService):
    name = "webshare"

    etc = ["webshare"]
    reloadable = True
    may_run_on_standby = False

    systemd_unit = "truenas-webshare-auth"
    systemd_async_start = True

    async def before_start(self) -> None:
        entitlement = await self.call2(self.s.truenas.entitlements.check, LicenseFeature.WEBSHARE)
        if not entitlement.entitled:
            raise CallError(f"webshare: {entitlement.message}")

    async def after_start(self) -> None:
        await self.call2(self.s.truesearch.configure)

    async def after_stop(self) -> None:
        await self.call2(self.s.truesearch.configure)
