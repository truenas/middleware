from __future__ import annotations

from truenas_pynetif.configure import (
    VlanConfig,
    configure_vlan as pynetif_configure_vlan,
)
from truenas_pynetif.netlink import ParentInterfaceNotFound
from middlewared.service import ServiceContext

__all__ = ("configure_vlans_impl",)


def configure_vlans_impl(
    ctx: ServiceContext,
    sock,
    parent_interfaces: list[str],
) -> list[str]:
    """Configure all VLAN interfaces from database.

    Args:
        ctx: Service context for middleware access
        sock: Netlink socket from netlink_route()
        parent_interfaces: List to track parent interfaces

    Returns:
        List of configured VLAN interface names
    """
    vlans = ctx.middleware.call_sync("datastore.query", "network.vlan")
    configured = []
    for vlan in vlans:
        name = vlan["vlan_vint"]
        try:
            configure_vlan_impl(ctx, sock, vlan, parent_interfaces)
            configured.append(name)
        except ParentInterfaceNotFound:
            ctx.logger.error(
                "VLAN %r parent interface %r not found, skipping.",
                name,
                vlan["vlan_pint"],
            )
        except Exception:
            ctx.logger.error("Error configuring VLAN %s", name, exc_info=True)
    return configured


def configure_vlan_impl(
    ctx: ServiceContext,
    sock,
    vlan: dict,
    parent_interfaces: list[str],
) -> None:
    """Configure a single VLAN interface.

    Args:
        ctx: Service context for middleware access
        sock: Netlink socket from netlink_route()
        vlan: Database record for the VLAN interface
        parent_interfaces: List to track parent interfaces
    """
    name = vlan["vlan_vint"]
    parent = vlan["vlan_pint"]
    ctx.logger.info("Configuring VLAN %s", name)
    # Track parent interface
    parent_interfaces.append(parent)
    # Create VlanConfig
    config = VlanConfig(
        name=name,
        parent=parent,
        tag=vlan["vlan_tag"],
        mtu=None,
    )
    ctx.logger.debug("Configuring %s with config: %r", name, config)
    pynetif_configure_vlan(sock, config)
