from __future__ import annotations

import ipaddress
import re
import socket

from truenas_pynetif.address.constants import AddressFamily
from truenas_pynetif.address.netlink import get_link_addresses, netlink_route
from truenas_pynetif.bits import InterfaceFlags
from truenas_pynetif.netif import get_interface
from truenas_pynetif.netlink import AddressInfo, LinkInfo

from middlewared.service import ServiceContext

from .sync_data import SyncData

__all__ = ("configure_addresses_impl",)


def _alias_to_addr(alias: dict) -> AddressInfo:
    """Convert alias dict to AddressInfo."""
    ip = ipaddress.ip_interface(f'{alias["address"]}/{alias["netmask"]}')
    return AddressInfo(
        family=AddressFamily.INET6 if ip.version == 6 else AddressFamily.INET,
        prefixlen=ip.network.prefixlen,
        address=str(ip.ip),
        broadcast=str(ip.network.broadcast_address),
    )


def _get_configured_addrs(name: str) -> set[AddressInfo]:
    """Get addresses currently configured on interface."""
    addrs = set()
    with netlink_route() as sock:
        for addr in get_link_addresses(sock, name):
            if addr.family != AddressFamily.LINK:
                addrs.add(addr)
    return addrs


def configure_addresses_impl(
    ctx: ServiceContext,
    sock: socket.socket,
    links: dict[str, LinkInfo],
    name: str,
    iface_config: dict,
    sync_data: SyncData,
) -> bool:
    """Configure IP addresses, MTU, and description for an interface.

    Args:
        ctx: Service context
        sock: Netlink socket
        links: Shared links dict
        name: Interface name
        iface_config: {"interface": {...}, "aliases": [...]}
        sync_data: Combined database data

    Returns:
        True if DHCP should be started for this interface.
    """
    data = iface_config["interface"]
    aliases = iface_config["aliases"]

    ctx.logger.info("Configuring addresses for %r", name)

    # Determine address keys based on failover node
    if sync_data.node == "B":
        addr_key = "int_address_b"
        alias_key = "alias_address_b"
    else:
        addr_key = "int_address"
        alias_key = "alias_address"

    addrs_configured = _get_configured_addrs(name)
    addrs_database = set()

    # Check DHCP status
    dhclient_run, dhclient_pid = ctx.middleware.call_sync("interface.dhclient_status", name)
    if dhclient_run and not data["int_dhcp"]:
        ctx.logger.debug("Stopping DHCP for %r", name)
        ctx.middleware.call_sync("interface.dhcp_stop", name)
    elif dhclient_run and data["int_dhcp"]:
        lease = ctx.middleware.call_sync("interface.dhclient_leases", name)
        if lease:
            _addr = re.search(r"fixed-address\s+(.+);", lease)
            _net = re.search(r"option subnet-mask\s+(.+);", lease)
            if _addr and _net:
                addrs_database.add(_alias_to_addr({
                    "address": _addr.group(1),
                    "netmask": _net.group(1),
                }))
            else:
                ctx.logger.info("Unable to get address from dhclient lease file for %r", name)

    # Add primary address from database
    if data[addr_key] and not data["int_dhcp"]:
        addrs_database.add(_alias_to_addr({
            "address": data[addr_key],
            "netmask": data["int_netmask"],
        }))

    # Add VIP if configured
    vip = data.get("int_vip", "")
    if vip:
        netmask = "32" if data["int_version"] == 4 else "128"
        addrs_database.add(_alias_to_addr({"address": vip, "netmask": netmask}))

    # Add alias addresses
    alias_vips = []
    for alias in aliases:
        addrs_database.add(_alias_to_addr({
            "address": alias[alias_key],
            "netmask": alias["alias_netmask"],
        }))
        if alias["alias_vip"]:
            alias_vip = alias["alias_vip"]
            alias_vips.append(alias_vip)
            netmask = "32" if alias["alias_version"] == 4 else "128"
            addrs_database.add(_alias_to_addr({"address": alias_vip, "netmask": netmask}))

    # Get interface object for modifications
    iface = get_interface(name)

    # Remove addresses not in database
    for addr in addrs_configured:
        address = addr.address
        if address.startswith("fe80::"):
            # Link-local addresses are fine, skip
            continue
        elif address == vip or address in alias_vips:
            # VIPs are managed by keepalived
            continue
        elif addr not in addrs_database:
            ctx.logger.debug("%s: removing %s", name, addr)
            iface.remove_address(addr)
        elif not data["int_dhcp"]:
            ctx.logger.debug("%s: removing possible valid_lft and preferred_lft on %s", name, addr)
            iface.replace_address(addr)

    # Configure IPv6 autoconf
    has_ipv6 = (
        data["int_version"] == 6
        or data["int_ipv6auto"]
        or any(alias["alias_version"] == 6 for alias in aliases)
    )
    autoconf = "1" if has_ipv6 else "0"
    ctx.middleware.call_sync("tunable.set_sysctl", f"net.ipv6.conf.{name}.autoconf", autoconf)

    # Handle keepalived for VIPs
    if vip or alias_vips:
        if not ctx.middleware.call_sync("service.started", "keepalived"):
            ctx.middleware.call_sync("service.control", "START", "keepalived").wait_sync(raise_error=True)
        else:
            ctx.middleware.call_sync("service.control", "RELOAD", "keepalived").wait_sync(raise_error=True)

    # Add addresses in database but not configured
    for addr in addrs_database - addrs_configured:
        address = addr.address
        if address == vip or address in alias_vips:
            # VIPs are managed by keepalived
            continue
        ctx.logger.debug("%s: adding %s", name, addr)
        iface.add_address(addr)

    # Configure MTU (skip for bond members)
    skip_mtu = sync_data.is_bond_member(name)
    if not skip_mtu:
        if data["int_mtu"]:
            if iface.mtu != data["int_mtu"]:
                iface.mtu = data["int_mtu"]
        elif iface.mtu != 1500:
            iface.mtu = 1500

    # Set interface description
    if data["int_name"] and iface.description != data["int_name"]:
        try:
            iface.description = data["int_name"]
        except Exception:
            ctx.logger.warning("Failed to set interface description on %s", name, exc_info=True)

    # Bring interface up
    if InterfaceFlags.UP not in iface.flags:
        iface.up()

    # Return True if DHCP should be started
    return not dhclient_run and data["int_dhcp"]
