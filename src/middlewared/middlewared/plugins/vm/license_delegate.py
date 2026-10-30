from __future__ import annotations

from typing import TYPE_CHECKING

from truenas_pylicensed.features import LicenseFeature

from middlewared.common.license_delegate import LicenseDelegate
from middlewared.utils.libvirt.utils import ACTIVE_STATES

if TYPE_CHECKING:
    from middlewared.main import Middleware


class VMsLicenseDelegate(LicenseDelegate):
    feature = LicenseFeature.VMS

    async def in_use(self) -> bool:
        return any(vm.status.state in ACTIVE_STATES for vm in await self.call2(self.s.vm.query))

    async def alert_lines(self, in_grace: bool) -> list[str]:
        vms = await self.call2(self.s.vm.query)
        if in_grace:
            names = [vm.name for vm in vms if vm.status.state in ACTIVE_STATES or vm.autostart]
            if not names:
                return []
            line = (
                f"Virtual machines: {', '.join(sorted(names))} keep running. Once stopped they cannot be started "
                "until the system is licensed for VMs."
            )
            if await self.middleware.call("failover.licensed"):
                line += " A failover starts the VMs that have autostart enabled."
            return [line]
        names = [vm.name for vm in vms if vm.autostart and vm.status.state not in ACTIVE_STATES]
        if not names:
            return []
        return [
            f"Virtual machines: {', '.join(sorted(names))} have autostart enabled but were not started because the "
            "system is not licensed for VMs. They start when the feature is licensed again."
        ]

    async def on_grant(self) -> None:
        await self.call2(self.s.vm.start_on_boot)


async def setup(middleware: Middleware) -> None:
    await middleware.call2(
        middleware.services.truenas.entitlements.register_license_delegate, VMsLicenseDelegate(middleware)
    )
