from __future__ import annotations

import socket

from truenas_pynetif.configure import (
    VlanConfig,
    configure_vlan as pynetif_configure_vlan,
)
from truenas_pynetif.netlink import LinkInfo, ParentInterfaceNotFound
from middlewared.service import ServiceContext

from .sync_data import SyncData

__all__ = ("configure_vlans_impl",)


def configure_vlans_impl(
    ctx: ServiceContext,
    sock: socket.socket,
    links: dict[str, LinkInfo],
    sync_data: SyncData,
) -> list[str]:
    """Configure all VLAN interfaces from database.

    Args:
        ctx: Service context
        sock: Netlink socket from netlink_route()
        links: Dict of LinkInfo objects from get_links()
        sync_data: Combined database data

    Returns:
        List of configured VLAN interface names
    """
    configured = []
    for vlan in sync_data.vlans:
        try:
            configure_vlan_impl(ctx, sock, links, vlan)
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
) -> None:
    """Configure a single VLAN interface.

    Args:
        ctx: Service context
        sock: Netlink socket from netlink_route()
        links: Dict of LinkInfo objects from get_links()
        vlan: Database record for the VLAN interface
    """
    ctx.logger.info("Configuring VLAN %s", vlan["vlan_vint"])
    config = VlanConfig(
        name=vlan["vlan_vint"],
        parent=vlan["vlan_pint"],
        tag=vlan["vlan_tag"],
    )
    ctx.logger.debug("Configuring %s with config: %r", vlan["vlan_vint"], config)
    pynetif_configure_vlan(sock, config, links)
