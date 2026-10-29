from __future__ import annotations

from typing import TYPE_CHECKING

from truenas_pylicensed.features import LicenseFeature

from middlewared.api.current import QueryOptions, ServiceOptions
from middlewared.common.license_delegate import LicenseDelegate

if TYPE_CHECKING:
    from middlewared.main import Middleware


class WebshareLicenseDelegate(LicenseDelegate):
    feature = LicenseFeature.WEBSHARE
    services = frozenset({"webshare"})

    async def alert_lines(self, in_grace: bool) -> list[str]:
        if in_grace:
            return [
                "WebShare: the service and logged-in users continue until the next reboot or an administrator "
                "restart of WebShare. After that it does not start until the system is licensed for WebShare."
            ]
        service = await self.call2(self.s.service.query, [["service", "=", "webshare"]], QueryOptions(get=True))
        if service.enable:
            return ["WebShare: the service is enabled but not started because the system is not licensed for WebShare."]
        return []

    async def on_grant(self) -> None:
        service = await self.call2(self.s.service.query, [["service", "=", "webshare"]], QueryOptions(get=True))
        if service.enable and not await self.call2(self.s.service.started, "webshare"):
            await (
                await self.call2(self.s.service.control, "START", "webshare", ServiceOptions(ha_propagate=False))
            ).wait(raise_error=True)


async def setup(middleware: Middleware) -> None:
    await middleware.call2(
        middleware.services.truenas.entitlements.register_license_delegate, WebshareLicenseDelegate(middleware)
    )
