from __future__ import annotations

from middlewared.service import ServiceContext
from truenas_pynetif.address.netlink import netlink_route

from .bond import configure_bonds_impl

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
        configured.extend(
            configure_bonds_impl(ctx, sock, parent_interfaces, sync_interface_opts)
        )
    return configured
