from __future__ import annotations

from middlewared.service import ServiceContext
from truenas_pynetif.address.get_links import get_links
from truenas_pynetif.address.netlink import netlink_route
from truenas_pynetif.netlink import LinkInfo

from .addresses import configure_addresses_impl
from .bond import configure_bonds_impl
from .bridge import configure_bridges_impl
from .sync_data import SyncData
from .vlan import configure_vlans_impl

__all__ = ("sync_impl",)


def sync_impl(
    ctx: ServiceContext,
    sync_data: SyncData,
) -> tuple[list[str], list[str]]:
    """Configure all interfaces from database to OS.

    Args:
        ctx: Service context
        sync_data: Combined database data

    Returns:
        Tuple of (configured_interface_names, interfaces_needing_dhcp)
    """
    configured = []
    run_dhcp = []

    with netlink_route() as sock:
        links: dict[str, LinkInfo] = get_links(sock)

        # 1. Configure bonds
        bond_names = configure_bonds_impl(ctx, sock, links, sync_data)
        for name in bond_names:
            configured.append(name)
            if name in sync_data.interfaces:
                try:
                    if configure_addresses_impl(ctx, sock, links, name, sync_data.interfaces[name], sync_data):
                        run_dhcp.append(name)
                except Exception:
                    ctx.logger.error("Failed to configure addresses for %s", name, exc_info=True)

        # 2. Configure physical interfaces (addresses only, no creation needed)
        for name, iface_config in sync_data.interfaces.items():
            if name.startswith(("bond", "vlan", "br")):
                continue  # Virtual interfaces handled separately
            try:
                if configure_addresses_impl(ctx, sock, links, name, iface_config, sync_data):
                    run_dhcp.append(name)
            except Exception:
                ctx.logger.error("Failed to configure addresses for %s", name, exc_info=True)

        # 3. Configure VLANs (after physical interfaces so parent MTU is set)
        vlan_names = configure_vlans_impl(ctx, sock, links, sync_data)
        for name in vlan_names:
            configured.append(name)
            if name in sync_data.interfaces:
                try:
                    if configure_addresses_impl(ctx, sock, links, name, sync_data.interfaces[name], sync_data):
                        run_dhcp.append(name)
                except Exception:
                    ctx.logger.error("Failed to configure addresses for %s", name, exc_info=True)

        # 4. Configure bridges
        bridge_names = configure_bridges_impl(ctx, sock, links, sync_data)
        for name in bridge_names:
            configured.append(name)
            if name in sync_data.interfaces:
                try:
                    if configure_addresses_impl(ctx, sock, links, name, sync_data.interfaces[name], sync_data):
                        run_dhcp.append(name)
                except Exception:
                    ctx.logger.error("Failed to configure addresses for %s", name, exc_info=True)

    return configured, run_dhcp
