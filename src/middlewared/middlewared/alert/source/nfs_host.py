from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Self

from middlewared.alert.base import Alert, AlertCategory, AlertClassConfig, AlertLevel, OneShotAlertClass

if TYPE_CHECKING:
    from middlewared.main import Middleware


async def load[T: OneShotAlertClass](middleware: Middleware, alerts: list[Alert[T]]) -> list[Alert[T]]:
    share_ids = {share["id"] for share in await middleware.call("datastore.query", "sharing.nfs_share")}
    return [alert for alert in alerts if getattr(alert.instance, "shareId", None) in share_ids]


@dataclass(kw_only=True)
class NFSHostnameLookupFailAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SHARING,
        level=AlertLevel.WARNING,
        title="NFS shares reference hosts that could not be resolved",
        text="NFS shares refer to the following unresolvable hosts: %(hosts)s",
        keys=[],
    )

    hosts: str

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return None


@dataclass(kw_only=True)
class NFSHostListExcessiveAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SHARING,
        level=AlertLevel.WARNING,
        title="NFS host list excessively long",
        text=(
            "The NFS share, %(sharePath)s, has %(numEntries)d host entries. "
            "A lengthy host list can lead to unexpected failures or performance issues. "
            "Consider using directory services, netgroups, network ranges, "
            "or other configurations to reduce the host list length."
        ),
        keys=["shareId"],
    )

    shareId: int | None = None
    sharePath: str
    numEntries: int

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return args["shareId"]

    @classmethod
    async def load(cls, middleware: Middleware, alerts: list[Alert[Self]]) -> list[Alert[Self]]:
        return await load(middleware, alerts)


@dataclass(kw_only=True)
class NFSNetworkListExcessiveAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SHARING,
        level=AlertLevel.WARNING,
        title="NFS network list excessively long",
        text=(
            "The NFS share, %(sharePath)s, has %(numEntries)d network entries. "
            "A lengthy network list can lead to unexpected failures or performance issues. "
            "Consider using directory services, netgroups, wider network ranges, "
            "or other configurations to reduce the network list length."
        ),
        keys=["shareId"],
    )

    shareId: int | None = None
    sharePath: str
    numEntries: int

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return args["shareId"]

    @classmethod
    async def load(cls, middleware: Middleware, alerts: list[Alert[Self]]) -> list[Alert[Self]]:
        return await load(middleware, alerts)
