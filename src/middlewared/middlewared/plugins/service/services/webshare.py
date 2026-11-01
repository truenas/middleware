from __future__ import annotations

from typing import TYPE_CHECKING

from truenas_pylicensed.features import LicenseFeature

from middlewared.service_exception import CallError, ValidationError

from .base import SimpleService

if TYPE_CHECKING:
    from middlewared.api.current import EntitlementEntry


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

    async def _entitlement(self) -> EntitlementEntry:
        return await self.call2(self.s.truenas.entitlements.check, LicenseFeature.WEBSHARE)

    async def before_enable(self) -> None:
        entitlement = await self._entitlement()
        if not entitlement.entitled:
            raise ValidationError("service_update.enable", entitlement.message)

    # strict: the unit state decides the next boot, where grace has ended
    async def may_enable_at_boot(self) -> bool:
        return (await self._entitlement()).entitled

    async def before_start(self) -> None:
        if not await self.call2(self.s.truenas.entitlements.serving, LicenseFeature.WEBSHARE):
            raise CallError('System is not licensed to use WebShare')

    async def after_start(self) -> None:
        await self.call2(self.s.truesearch.configure)

    async def after_stop(self) -> None:
        await self.call2(self.s.truesearch.configure)
