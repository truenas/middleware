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
            "Self-encrypting drives are configured but the system is not licensed for SED. Drives already set up "
            "as SED are still unlocked, and disks detected as SED while the system was licensed can still be added "
            "to an all-SED pool. Disks inserted after the license lapsed are not checked for SED support and "
            "cannot be added. Creating an all-SED pool or setting up a new SED drive requires a license."
        ]


async def setup(middleware: Middleware) -> None:
    await middleware.call2(
        middleware.services.truenas.entitlements.register_license_delegate, SedLicenseDelegate(middleware)
    )
