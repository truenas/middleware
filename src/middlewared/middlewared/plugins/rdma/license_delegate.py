from __future__ import annotations

from typing import TYPE_CHECKING

from truenas_pylicensed.features import LicenseFeature

from middlewared.api.current import ServiceOptions
from middlewared.common.license_delegate import LicenseDelegate

if TYPE_CHECKING:
    from middlewared.main import Middleware


class RdmaLicenseDelegate(LicenseDelegate):
    feature = LicenseFeature.RDMA
    services = frozenset({"nfs", "iscsitarget", "nvmet", "nvmf"})

    async def alert_lines(self, in_grace: bool) -> list[str]:
        protocols = []
        if (await self.call2(self.s.nfs.config)).rdma:
            protocols.append("NFS")
        if (await self.middleware.call("iscsi.global.config"))["iser"]:
            protocols.append("iSER")
        if (await self.middleware.call("nvmet.global.config"))["rdma"]:
            protocols.append("NVMe-oF")
        if not protocols:
            return []
        names = ", ".join(sorted(protocols))
        if in_grace:
            return [
                f"RDMA ({names}): RDMA connections stop at the next reboot or a restart of the NFS, iSCSI or "
                "NVMe-oF service. Move RDMA clients to TCP first."
            ]
        return [f"RDMA ({names}): RDMA listeners are not opened because the system is not licensed for RDMA."]

    async def on_grant(self) -> None:
        if (await self.call2(self.s.nfs.config)).rdma:
            await (await self.call2(self.s.service.control, "RELOAD", "nfs", ServiceOptions(ha_propagate=False))).wait(
                raise_error=True
            )


async def setup(middleware: Middleware) -> None:
    await middleware.call2(
        middleware.services.truenas.entitlements.register_license_delegate, RdmaLicenseDelegate(middleware)
    )
