from __future__ import annotations

import socket

from truenas_pynetif.configure import (
    VlanConfig,
    configure_vlan as pynetif_configure_vlan,
)
from truenas_pynetif.netlink import LinkInfo, ParentInterfaceNotFound
from middlewared.service import ServiceContext

__all__ = ("configure_vlans_impl",)


def configure_vlans_impl(
    ctx: ServiceContext,
    sock: socket.socket,
    links: dict[str, LinkInfo],
    parent_interfaces: list[str],
) -> list[str]:
    """Configure all VLAN interfaces from database.

    Args:
        ctx: Service context for middleware access
        sock: Netlink socket from netlink_route()
        links: Dict of LinkInfo objects from get_links()
        parent_interfaces: List to track parent interfaces

    Returns:
        List of configured VLAN interface names
    """
    vlans = ctx.middleware.call_sync("datastore.query", "network.vlan")
    configured = []
    for vlan in vlans:
        try:
            configure_vlan_impl(ctx, sock, links, vlan, parent_interfaces)
            configured.append(vlan["vlan_vint"])
        except ParentInterfaceNotFound:
            ctx.logger.error(
                "VLAN %r parent interface %r not found, skipping.",
                vlan["vlan_vint"],
                vlan["vlan_pint"],
            )
        except Exception:
            ctx.logger.error(
                "Error configuring VLAN %s", vlan["vlan_vint"], exc_info=True
            )
    return configured


def configure_vlan_impl(
    ctx: ServiceContext,
    sock: socket.socket,
    links: dict[str, LinkInfo],
    vlan: dict,
    parent_interfaces: list[str],
) -> None:
    """Configure a single VLAN interface.

    Args:
        ctx: Service context for middleware access
        sock: Netlink socket from netlink_route()
        links: Dict of LinkInfo objects from get_links()
        vlan: Database record for the VLAN interface
        parent_interfaces: List to track parent interfaces
    """
    ctx.logger.info("Configuring VLAN %s", vlan["vlan_vint"])
    # Create VlanConfig
    config = VlanConfig(
        name=vlan["vlan_vint"], parent=vlan["vlan_pint"], tag=vlan["vlan_tag"]
    )
    ctx.logger.debug("Configuring %s with config: %r", vlan["vlan_vint"], config)
    pynetif_configure_vlan(sock, config, links)
    parent_interfaces.append(vlan["vlan_pint"])
