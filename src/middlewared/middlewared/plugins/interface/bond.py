from __future__ import annotations

import socket

from truenas_pynetif.configure import (
    BondConfig,
    configure_bond as pynetif_configure_bond,
)
from truenas_pynetif.address.bond import BondXmitHashPolicy, BondLacpRate
from truenas_pynetif.netlink import LinkInfo
from middlewared.service import ServiceContext

from .sync_data import SyncData

__all__ = ("configure_bonds_impl",)


def configure_bonds_impl(
    ctx: ServiceContext,
    sock: socket.socket,
    links: dict[str, LinkInfo],
    sync_data: SyncData,
) -> list[str]:
    """Configure all bond interfaces from database.

    Args:
        ctx: Service context
        sock: Netlink socket from netlink_route()
        links: Dict of LinkInfo objects from get_links()
        sync_data: Combined database data

    Returns:
        List of configured bond interface names
    """
    configured = []
    for bond in sync_data.bonds:
        name = bond["lagg_interface"]["int_interface"]
        members = sync_data.get_bond_members_for(bond["id"])
        try:
            configure_bond_impl(ctx, sock, links, sync_data, bond, members)
            configured.append(name)
        except Exception:
            ctx.logger.error("Error configuring bond %s", name, exc_info=True)
    return configured


def configure_bond_impl(
    ctx: ServiceContext,
    sock: socket.socket,
    links: dict[str, LinkInfo],
    sync_data: SyncData,
    bond: dict,
    members: list[dict],
) -> None:
    """Configure a single bond interface.

    Args:
        ctx: Service context
        sock: Netlink socket from netlink_route()
        links: Dict of LinkInfo objects from get_links()
        sync_data: Combined database data
        bond: Database record for the bond interface
        members: List of member interface records
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

    # Build member list (ordered by lagg_ordernum)
    members_sorted = sorted(members, key=lambda m: m["lagg_ordernum"])
    member_names = [m["lagg_physnic"] for m in members_sorted]

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

    # Get MTU from interface record
    mtu = bond["lagg_interface"].get("int_mtu") or 1500

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
