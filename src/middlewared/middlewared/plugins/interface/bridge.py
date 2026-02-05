from __future__ import annotations

import socket

from truenas_pynetif.configure import (
    BridgeConfig,
    configure_bridge as pynetif_configure_bridge,
)
from truenas_pynetif.netlink import LinkInfo
from middlewared.service import ServiceContext

__all__ = ("configure_bridges_impl",)


def configure_bridges_impl(
    ctx: ServiceContext,
    sock: socket.socket,
    links: dict[str, LinkInfo],
    parent_interfaces: list[str],
) -> list[str]:
    """Configure all bridge interfaces from database.

    Args:
        ctx: Service context for middleware access
        sock: Netlink socket from netlink_route()
        links: Dict of LinkInfo objects from get_links()
        parent_interfaces: List to track parent interfaces

    Returns:
        List of configured bridge interface names
    """
    bridges = ctx.middleware.call_sync("datastore.query", "network.bridge")
    configured = []
    for bridge in bridges:
        try:
            configure_bridge_impl(ctx, sock, links, bridge, parent_interfaces)
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
    parent_interfaces: list[str],
) -> None:
    """Configure a single bridge interface.

    Args:
        ctx: Service context for middleware access
        sock: Netlink socket from netlink_route()
        links: Dict of LinkInfo objects from get_links()
        bridge: Database record for the bridge interface
        parent_interfaces: List to track parent interfaces
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
    parent_interfaces.extend(bridge["members"])
