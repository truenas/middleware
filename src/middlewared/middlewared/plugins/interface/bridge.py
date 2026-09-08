from __future__ import annotations

import socket

from truenas_pynetif.address.get_links import get_link
from truenas_pynetif.configure import (
    BridgeConfig,
    configure_bridge as pynetif_configure_bridge,
)
from truenas_pynetif.netlink import DeviceNotFound, LinkInfo
from middlewared.service import ServiceContext

from .sync_data import SyncData

__all__ = ("configure_bridges_impl",)


def configure_bridges_impl(
    ctx: ServiceContext,
    sock: socket.socket,
    links: dict[str, LinkInfo],
    sync_data: SyncData,
) -> tuple[list[str], list[str]]:
    """Configure all bridge interfaces from database.

    Args:
        ctx: Service context
        sock: Netlink socket from netlink_route()
        links: Dict of LinkInfo objects from get_links()
        sync_data: Combined database data

    Returns:
        Tuple of (configured bridge interface names, descriptions of bridges that failed)
    """
    configured = []
    failures = []
    for bridge in sync_data.bridges:
        name = bridge["interface"]["int_interface"]
        try:
            configure_bridge_impl(ctx, sock, links, bridge)
            configured.append(name)
        except Exception as e:
            ctx.logger.error("Error configuring bridge %s", name, exc_info=True)
            failures.append(describe_bridge_failure(sock, name, bridge["members"], e))
    return configured, failures


def describe_bridge_failure(sock: socket.socket, name: str, members: list[str], error: Exception) -> str:
    """Describe a failed bridge configuration, naming the members that were not enslaved.

    The netlink error alone does not say which member was refused, and the
    kernel gives no reason beyond an errno (EBUSY, for one, means the member
    already hosts macvlan/macvtap ports).

    Args:
        sock: Netlink socket from netlink_route()
        name: Bridge interface name
        members: Members the bridge should have
        error: Exception raised while configuring the bridge

    Returns:
        One-line description suitable for an error message
    """
    try:
        bridge_index = get_link(sock, name).index
    except DeviceNotFound:
        return f"{name}: failed to create bridge ({error})"

    missing = []
    for member in members:
        try:
            if get_link(sock, member).master != bridge_index:
                missing.append(member)
        except DeviceNotFound:
            missing.append(member)

    if missing:
        return f"{name}: failed to add member(s) {', '.join(missing)} ({error})"
    return f"{name}: {error}"


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
