from __future__ import annotations

from typing import TYPE_CHECKING

from truenas_pylicensed.features import LicenseFeature

from middlewared.common.license_delegate import LicenseDelegate
from middlewared.utils.libvirt.utils import ACTIVE_STATES

if TYPE_CHECKING:
    from middlewared.main import Middleware


class ContainersLicenseDelegate(LicenseDelegate):
    feature = LicenseFeature.CONTAINERS

    async def in_use(self) -> bool:
        return any(container.status.state in ACTIVE_STATES for container in await self.call2(self.s.container.query))

    async def alert_lines(self, in_grace: bool) -> list[str]:
        containers = await self.call2(self.s.container.query)
        if in_grace:
            names = [c.name for c in containers if c.status.state in ACTIVE_STATES or c.autostart]
            if not names:
                return []
            return [
                f"Containers: {', '.join(sorted(names))} keep running. Once stopped they cannot be started until "
                "the system is licensed for containers. A failover starts the containers that have autostart enabled."
            ]
        names = [c.name for c in containers if c.autostart and c.status.state not in ACTIVE_STATES]
        if not names:
            return []
        return [
            f"Containers: {', '.join(sorted(names))} have autostart enabled but were not started because the system "
            "is not licensed for containers. They start when the feature is licensed again."
        ]

    async def on_grant(self) -> None:
        await self.call2(self.s.container.migrate_and_start_on_boot)


async def setup(middleware: Middleware) -> None:
    await middleware.call2(
        middleware.services.truenas.entitlements.register_license_delegate, ContainersLicenseDelegate(middleware)
    )
