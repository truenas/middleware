from __future__ import annotations

import socket

from truenas_pynetif.configure import (
    BondConfig,
    configure_bond as pynetif_configure_bond,
)
from truenas_pynetif.address.bond import BondXmitHashPolicy, BondLacpRate
from truenas_pynetif.netlink import LinkInfo
from middlewared.service import ServiceContext

__all__ = ("configure_bonds_impl",)


def configure_bonds_impl(
    ctx: ServiceContext,
    sock: socket.socket,
    links: dict[str, LinkInfo],
    parent_interfaces: list[str],
    sync_interface_opts: dict,
) -> list[str]:
    """Configure all bond interfaces from database.

    Args:
        ctx: Service ctx for middleware access
        sock: Netlink socket from netlink_route()
        links: Dict of LinkInfo objects from get_links()
        parent_interfaces: List to track parent interfaces
        sync_interface_opts: Dict of interface sync options

    Returns:
        List of configured bond interface names
    """
    bonds = ctx.middleware.call_sync("datastore.query", "network.lagginterface")
    configured = []
    for bond in bonds:
        name = bond["lagg_interface"]["int_interface"]
        members = ctx.middleware.call_sync(
            "datastore.query",
            "network.lagginterfacemembers",
            [("lagg_interfacegroup_id", "=", bond["id"])],
            {"order_by": ["lagg_ordernum"]},
        )
        try:
            configure_bond_impl(
                ctx, sock, links, bond, members, parent_interfaces, sync_interface_opts
            )
            configured.append(name)
        except Exception:
            ctx.logger.error("Error configuring bond %s", name, exc_info=True)
    return configured


def configure_bond_impl(
    ctx: ServiceContext,
    sock: socket.socket,
    links: dict[str, LinkInfo],
    bond: dict,
    members: list[dict],
    parent_interfaces: list[str],
    sync_interface_opts: dict,
) -> None:
    """Configure a single bond interface.

    Args:
        ctx: Service ctx for middleware access
        sock: Netlink socket from netlink_route()
        links: Dict of LinkInfo objects from get_links()
        bond: Database record for the bond interface
        members: List of member interface records
        parent_interfaces: List to track parent interfaces
        sync_interface_opts: Dict of interface sync options
    """
    name = bond["lagg_interface"]["int_interface"]
    ctx.logger.info("Configuring bond %s", name)

    # Map database protocol to BondConfig mode
    protocol_map = {
        "LACP": "LACP",
        "FAILOVER": "FAILOVER",
        "LOADBALANCE": "LOADBALANCE",
    }
    mode = protocol_map.get(bond["lagg_protocol"].upper())
    if not mode:
        raise ValueError(f"Unsupported bond protocol: {bond['lagg_protocol']}")

    # Build member list
    member_names = [m["lagg_physnic"] for m in members]

    # Mark members to skip MTU (handled by bond)
    for member_name in member_names:
        sync_interface_opts[member_name]["skip_mtu"] = True
        parent_interfaces.append(member_name)

    # Map xmit_hash_policy to enum
    xmit_hash_policy = None
    if lxhp := bond.get("lagg_xmit_hash_policy"):
        xmit_hash_policy = getattr(BondXmitHashPolicy, lxhp.upper(), None)

    # Map lacpdu_rate to enum
    lacpdu_rate = None
    if llr := bond.get("lagg_lacpdu_rate"):
        lacpdu_rate = getattr(BondLacpRate, llr.upper(), None)

    # Get primary interface for FAILOVER mode
    primary = member_names[0] if mode == "FAILOVER" and member_names else None

    # Get MTU from sync_interface_opts if available
    mtu = sync_interface_opts.get(name, {}).get("mtu", 1500)

    # Create BondConfig
    config = BondConfig(
        name=name,
        mode=mode,
        members=member_names,
        xmit_hash_policy=xmit_hash_policy,
        lacpdu_rate=lacpdu_rate,
        miimon=100,
        primary=primary,
        mtu=mtu,
    )

    ctx.logger.debug("Configuring %s with config: %r", name, config)
    pynetif_configure_bond(sock, config, links)
