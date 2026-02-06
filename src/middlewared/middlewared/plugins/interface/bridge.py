from __future__ import annotations

import socket

from truenas_pynetif.configure import (
    BridgeConfig,
    configure_bridge as pynetif_configure_bridge,
)
from truenas_pynetif.netlink import LinkInfo
from middlewared.service import ServiceContext

from .sync_data import SyncData

__all__ = ("configure_bridges_impl",)


def configure_bridges_impl(
    ctx: ServiceContext,
    sock: socket.socket,
    links: dict[str, LinkInfo],
    sync_data: SyncData,
) -> list[str]:
    """Configure all bridge interfaces from database.

    Args:
        ctx: Service context
        sock: Netlink socket from netlink_route()
        links: Dict of LinkInfo objects from get_links()
        sync_data: Combined database data

    Returns:
        List of configured bridge interface names
    """
    configured = []
    for bridge in sync_data.bridges:
        try:
            configure_bridge_impl(ctx, sock, links, bridge)
            configured.append(bridge["interface"]["int_interface"])
        except Exception:
            ctx.logger.error(
                "Error configuring bridge %s",
                bridge["interface"]["int_interface"],
                exc_info=True,
            )
    return configured


def configure_bridge_impl(
    ctx: ServiceContext,
    sock: socket.socket,
    links: dict[str, LinkInfo],
    bridge: dict,
) -> None:
    """Configure a single bridge interface.

    Args:
        ctx: Service context
        sock: Netlink socket from netlink_route()
        links: Dict of LinkInfo objects from get_links()
        bridge: Database record for the bridge interface
    """
    name = bridge["interface"]["int_interface"]
    ctx.logger.info("Configuring bridge %s", name)
    config = BridgeConfig(
        name=name,
        members=bridge["members"],
        stp=bridge["stp"],
        mtu=bridge["interface"]["int_mtu"] or None,
        enable_learning=bridge.get("enable_learning", True),
        preserve_member_prefixes=("vnet",),
    )
    ctx.logger.debug("Configuring %s with config: %r", name, config)
    pynetif_configure_bridge(sock, config, links)
