from __future__ import annotations

from middlewared.service import ServiceContext
from truenas_pynetif.address.get_links import get_links
from truenas_pynetif.address.netlink import netlink_route
from truenas_pynetif.netlink import LinkInfo

from .bond import configure_bonds_impl
from .bridge import configure_bridges_impl
from .vlan import configure_vlans_impl

__all__ = ("sync_impl",)


def sync_impl(
    ctx: ServiceContext, parent_interfaces: list, sync_interface_opts: dict
) -> list[str]:
    """Configure interfaces that are in the database to the OS.

    Args:
        parent_interfaces: List to track parent interfaces
        sync_interface_opts: Dict of interface sync options

    Returns:
        List of configured interface names
    """
    configured = []
    with netlink_route() as sock:
        links: dict[str, LinkInfo] = get_links(sock)

        # Configure bonds
        configured.extend(
            configure_bonds_impl(ctx, sock, links, parent_interfaces, sync_interface_opts)
        )

        # Configure VLANs
        configured.extend(configure_vlans_impl(ctx, sock, links, parent_interfaces))

        # Configure bridges
        configured.extend(configure_bridges_impl(ctx, sock, links, parent_interfaces))

    return configured
