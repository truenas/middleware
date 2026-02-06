from __future__ import annotations

import socket

from truenas_pynetif.address.address import flush_addresses
from truenas_pynetif.address.link import delete_link, set_link_down
from truenas_pynetif.netlink import LinkInfo

from middlewared.service import ServiceContext

from .sync_data import SyncData

__all__ = ("unconfigure_impl",)

_VIRTUAL_PREFIXES = ("br", "bond", "vlan")


def unconfigure_impl(
    ctx: ServiceContext,
    sock: socket.socket,
    links: dict[str, LinkInfo],
    name: str,
    cloned_interfaces: list[str],
    sync_data: SyncData,
) -> None:
    """Remove addresses and optionally delete or bring down an interface.

    Flushes all global-scope IP addresses, stops DHCP if running, and either
    deletes virtual interfaces (bridge/bond/vlan) or brings down physical
    interfaces depending on whether they were just configured or are parent
    interfaces of other virtual interfaces.

    Args:
        ctx: Service context
        sock: Netlink socket
        links: Current links from get_links()
        name: Interface name to unconfigure
        cloned_interfaces: Virtual interfaces that were just configured
        sync_data: Database data (for parent_interfaces check)
    """
    if name not in links:
        return

    link = links[name]
    ctx.logger.info("Unconfiguring interface %r", name)

    flush_addresses(sock, index=link.index)

    dhclient_running, _ = ctx.middleware.call_sync("interface.dhclient_status", name)
    if dhclient_running:
        ctx.middleware.call_sync("interface.dhcp_stop", name)

    if name not in cloned_interfaces and name.startswith(_VIRTUAL_PREFIXES):
        delete_link(sock, index=link.index)
    elif name not in sync_data.parent_interfaces:
        set_link_down(sock, index=link.index)
