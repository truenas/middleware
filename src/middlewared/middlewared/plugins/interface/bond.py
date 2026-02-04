from __future__ import annotations

from truenas_pynetif.configure import BondConfig, configure_bond as pynetif_configure_bond
from truenas_pynetif.address.bond import BondXmitHashPolicy, BondLacpRate
from middlewared.service import ServiceContext

__all__ = ("configure_bond_impl", "configure_bonds_impl")


def configure_bonds_impl(
    context: ServiceContext,
    sock,
    parent_interfaces: list[str],
    sync_interface_opts: dict
) -> list[str]:
    """Configure all bond interfaces from database.

    Args:
        context: Service context for middleware access
        sock: Netlink socket from netlink_route()
        parent_interfaces: List to track parent interfaces
        sync_interface_opts: Dict of interface sync options

    Returns:
        List of configured bond interface names
    """
    laggs = context.middleware.call_sync('datastore.query', 'network.lagginterface')
    configured = []

    for lagg in laggs:
        name = lagg['lagg_interface']['int_interface']
        members = context.middleware.call_sync(
            'datastore.query',
            'network.lagginterfacemembers',
            [('lagg_interfacegroup_id', '=', lagg['id'])],
            {'order_by': ['lagg_ordernum']}
        )

        try:
            configure_bond_impl(context, sock, lagg, members, parent_interfaces, sync_interface_opts)
            configured.append(name)
        except Exception:
            context.logger.error('Error configuring bond %s', name, exc_info=True)

    return configured


def configure_bond_impl(
    context: ServiceContext,
    sock,
    lagg: dict,
    members: list[dict],
    parent_interfaces: list[str],
    sync_interface_opts: dict
) -> None:
    """Configure a single bond interface.

    Args:
        context: Service context for middleware access
        sock: Netlink socket from netlink_route()
        lagg: Database record for the bond interface
        members: List of member interface records
        parent_interfaces: List to track parent interfaces
        sync_interface_opts: Dict of interface sync options
    """
    name = lagg['lagg_interface']['int_interface']
    context.logger.info('Configuring bond %s', name)

    # Map database protocol to BondConfig mode
    protocol_map = {
        'LACP': 'LACP',
        'FAILOVER': 'FAILOVER',
        'LOADBALANCE': 'LOADBALANCE',
    }
    mode = protocol_map.get(lagg['lagg_protocol'].upper())
    if not mode:
        raise ValueError(f"Unsupported bond protocol: {lagg['lagg_protocol']}")

    # Build member list
    member_names = [m['lagg_physnic'] for m in members]

    # Mark members to skip MTU (handled by bond)
    for member_name in member_names:
        sync_interface_opts[member_name]['skip_mtu'] = True
        parent_interfaces.append(member_name)

    # Map xmit_hash_policy to enum
    xmit_hash_policy = None
    if lxhp := lagg.get('lagg_xmit_hash_policy'):
        xmit_hash_policy = getattr(BondXmitHashPolicy, lxhp.upper(), None)

    # Map lacpdu_rate to enum
    lacpdu_rate = None
    if llr := lagg.get('lagg_lacpdu_rate'):
        lacpdu_rate = getattr(BondLacpRate, llr.upper(), None)

    # Get primary interface for FAILOVER mode
    primary = member_names[0] if mode == 'FAILOVER' and member_names else None

    # Get MTU from sync_interface_opts if available
    mtu = sync_interface_opts.get(name, {}).get('mtu', 1500)

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

    context.logger.debug('Configuring %s with config: %r', name, config)
    pynetif_configure_bond(sock, config)
