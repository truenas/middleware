from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.alert.source.nfs_host import NFSHostListExcessiveAlert, NFSNetworkListExcessiveAlert
from middlewared.api.current import SharingNFSEntry

if TYPE_CHECKING:
    from middlewared.main import Middleware

NETWORKS_WARNING_THRESHOLD = 100
HOSTS_WARNING_THRESHOLD = 100


async def sync_share_alerts(middleware: Middleware, share: SharingNFSEntry) -> None:
    if len(share.networks) >= NETWORKS_WARNING_THRESHOLD:
        await middleware.call2(
            middleware.services.alert.oneshot_create,
            NFSNetworkListExcessiveAlert(shareId=share.id, sharePath=share.path, numEntries=len(share.networks)),
        )
    else:
        await middleware.call2(
            middleware.services.alert.oneshot_delete, "NFSNetworkListExcessive", {"shareId": share.id}
        )

    if len(share.hosts) >= HOSTS_WARNING_THRESHOLD:
        await middleware.call2(
            middleware.services.alert.oneshot_create,
            NFSHostListExcessiveAlert(shareId=share.id, sharePath=share.path, numEntries=len(share.hosts)),
        )
    else:
        await middleware.call2(middleware.services.alert.oneshot_delete, "NFSHostListExcessive", {"shareId": share.id})


async def remove_share_alerts(middleware: Middleware, share_id: int) -> None:
    await middleware.call2(middleware.services.alert.oneshot_delete, "NFSNetworkListExcessive", {"shareId": share_id})
    await middleware.call2(middleware.services.alert.oneshot_delete, "NFSHostListExcessive", {"shareId": share_id})
