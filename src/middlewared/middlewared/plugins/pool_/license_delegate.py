from __future__ import annotations

from typing import TYPE_CHECKING

from truenas_pylicensed.features import LicenseFeature

from middlewared.common.license_delegate import LicenseDelegate

if TYPE_CHECKING:
    from middlewared.main import Middleware


class SedLicenseDelegate(LicenseDelegate):
    feature = LicenseFeature.SED

    async def alert_lines(self, in_grace: bool) -> list[str]:
        if not await self.middleware.call("system.sed_credentials_exist"):
            return []
        return [
            "Self-encrypting drives: drives are in use without a license. Drives already set up as SED keep being "
            "unlocked. New drives are not detected as SED until the system is licensed, "
            "so disks cannot be added to or replaced in an all-SED pool."
        ]


async def setup(middleware: Middleware) -> None:
    await middleware.call2(
        middleware.services.truenas.entitlements.register_license_delegate, SedLicenseDelegate(middleware)
    )
