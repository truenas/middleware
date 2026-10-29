from __future__ import annotations

from typing import TYPE_CHECKING

from truenas_pylicensed.features import LicenseFeature

from middlewared.common.license_delegate import LicenseDelegate
from middlewared.plugins.iscsi_.targets import MODE_FC_CAPABLE

if TYPE_CHECKING:
    from middlewared.main import Middleware


class FibreChannelLicenseDelegate(LicenseDelegate):
    feature = LicenseFeature.FIBRECHANNEL
    services = frozenset({"iscsitarget"})

    async def alert_lines(self, in_grace: bool) -> list[str]:
        targets = await self.middleware.call("iscsi.target.query", [["mode", "in", MODE_FC_CAPABLE]])
        if not targets:
            return []
        names = ", ".join(sorted(target["name"] for target in targets))
        if in_grace:
            ports = ", ".join(sorted(port["port"] for port in await self.middleware.call("fcport.query")))
            on_ports = f" on ports {ports}" if ports else ""
            return [
                f"Fibre Channel: targets {names}{on_ports} stop being served over Fibre Channel at the next reboot "
                "or iSCSI service restart. Move hosts off these paths first."
            ]
        return [
            f"Fibre Channel: targets {names} are not served over Fibre Channel because the system is not licensed "
            "for Fibre Channel."
        ]

    async def on_grant(self) -> None:
        await self.middleware.call("fc.fc_host.reset_wired", True)


async def setup(middleware: Middleware) -> None:
    await middleware.call2(
        middleware.services.truenas.entitlements.register_license_delegate, FibreChannelLicenseDelegate(middleware)
    )
