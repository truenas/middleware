from __future__ import annotations

from typing import TYPE_CHECKING

from truenas_pylicensed.features import LicenseFeature

from middlewared.common.license_delegate import LicenseDelegate

if TYPE_CHECKING:
    from middlewared.main import Middleware


class AppsLicenseDelegate(LicenseDelegate):
    feature = LicenseFeature.APPS
    services = frozenset({"docker"})

    async def alert_lines(self, in_grace: bool) -> list[str]:
        if in_grace:
            return [
                "Applications: Docker and its running apps keep running until the next reboot or a Docker stop or "
                "restart. A stopped app cannot be started until the system is licensed for Applications."
            ]
        if (await self.call2(self.s.docker.config)).pool:
            return [
                "Applications: Docker and its apps are not started because the system is not licensed for "
                "Applications. They start when the feature is licensed again."
            ]
        return []

    async def on_grant(self) -> None:
        if (await self.call2(self.s.docker.config)).pool and not await self.call2(self.s.service.started, "docker"):
            await self.call2(self.s.docker.start_service, True)


async def setup(middleware: Middleware) -> None:
    await middleware.call2(
        middleware.services.truenas.entitlements.register_license_delegate, AppsLicenseDelegate(middleware)
    )
