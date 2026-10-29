from __future__ import annotations

from typing import TYPE_CHECKING

from truenas_pylicensed.features import LicenseFeature

from middlewared.common.license_delegate import LicenseDelegate

if TYPE_CHECKING:
    from middlewared.main import Middleware


class NfsSnapshotLicenseDelegate(LicenseDelegate):
    feature = LicenseFeature.NFS_SNAPSHOT
    services = frozenset({"nfs"})

    async def alert_lines(self, in_grace: bool) -> list[str]:
        shares = await self.call2(self.s.sharing.nfs.query, [["expose_snapshots", "=", True]])
        if not shares:
            return []
        paths = ", ".join(sorted(share.path for share in shares))
        if in_grace:
            return [
                f"NFS: the snapshot directory of shares {paths} stays visible until the next reboot or NFS service "
                "restart. After that it is hidden until the system is licensed for NFS snapshot exposure."
            ]
        return [
            f"NFS: the snapshot directory of shares {paths} is hidden because the system is not licensed for NFS "
            "snapshot exposure."
        ]


async def setup(middleware: Middleware) -> None:
    await middleware.call2(
        middleware.services.truenas.entitlements.register_license_delegate, NfsSnapshotLicenseDelegate(middleware)
    )
