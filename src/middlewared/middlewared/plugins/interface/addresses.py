from __future__ import annotations

import ipaddress
import re
import socket

from truenas_pynetif.address.address import add_address, remove_address, replace_address
from truenas_pynetif.address.constants import AddressFamily, IFFlags
from truenas_pynetif.address.get_ipaddresses import get_link_addresses
from truenas_pynetif.address.link import set_link_alias, set_link_mtu, set_link_up
from truenas_pynetif.netlink import AddressInfo, LinkInfo

from middlewared.service import ServiceContext

from .sync_data import SyncData

__all__ = ("configure_addresses_impl",)

_DHCP_FIXED_ADDR_RE = re.compile(r"fixed-address\s+(.+);")
_DHCP_SUBNET_MASK_RE = re.compile(r"option subnet-mask\s+(.+);")


def _alias_to_addr(alias: dict) -> AddressInfo:
    """Convert alias dict to AddressInfo."""
    ip = ipaddress.ip_interface(f"{alias['address']}/{alias['netmask']}")
    return AddressInfo(
        family=AddressFamily.INET6 if ip.version == 6 else AddressFamily.INET,
        prefixlen=ip.network.prefixlen,
        address=str(ip.ip),
        broadcast=str(ip.network.broadcast_address),
    )


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
    link = links[name]
    link_index = link.index
    if sync_data.node == "B":
        addr_key = "int_address_b"
        alias_key = "alias_address_b"
    else:
        addr_key = "int_address"
        alias_key = "alias_address"

    # Get currently configured addresses using
    # index to avoid name lookup syscall
    addrs_configured = {
        addr
        for addr in get_link_addresses(sock, index=link_index)
        if addr.family != AddressFamily.LINK
    }
    addrs_database = set()

    # Check DHCP status
    dhclient_run, dhclient_pid = ctx.middleware.call_sync(
        "interface.dhclient_status", name
    )
    if dhclient_run and not data["int_dhcp"]:
        ctx.logger.debug("Stopping DHCP for %r", name)
        ctx.middleware.call_sync("interface.dhcp_stop", name)
    elif dhclient_run and data["int_dhcp"]:
        lease = ctx.middleware.call_sync("interface.dhclient_leases", name)
        if lease:
            _addr = _DHCP_FIXED_ADDR_RE.search(lease)
            _net = _DHCP_SUBNET_MASK_RE.search(lease)
            if _addr and _net:
                addrs_database.add(
                    _alias_to_addr(
                        {
                            "address": _addr.group(1),
                            "netmask": _net.group(1),
                        }
                    )
                )
            else:
                ctx.logger.info(
                    "Unable to get address from dhclient lease file for %r", name
                )

    # Add primary address from database
    if data[addr_key] and not data["int_dhcp"]:
        addrs_database.add(
            _alias_to_addr(
                {
                    "address": data[addr_key],
                    "netmask": data["int_netmask"],
                }
            )
        )

    # Add VIP if configured
    vip = data.get("int_vip", "")
    if vip:
        netmask = "32" if data["int_version"] == 4 else "128"
        addrs_database.add(_alias_to_addr({"address": vip, "netmask": netmask}))

    # Add alias addresses
    alias_vips = []
    for alias in aliases:
        addrs_database.add(
            _alias_to_addr(
                {
                    "address": alias[alias_key],
                    "netmask": alias["alias_netmask"],
                }
            )
        )
        if alias["alias_vip"]:
            alias_vip = alias["alias_vip"]
            alias_vips.append(alias_vip)
            netmask = "32" if alias["alias_version"] == 4 else "128"
            addrs_database.add(
                _alias_to_addr({"address": alias_vip, "netmask": netmask})
            )

    # Remove addresses not in database
    for addr in addrs_configured:
        address = addr.address
        if address.startswith("fe80::"):
            continue
        elif address == vip or address in alias_vips:
            continue
        elif addr not in addrs_database:
            ctx.logger.debug("%s: removing %s", name, addr)
            remove_address(sock, addr.address, addr.prefixlen, index=link_index)
        elif not data["int_dhcp"]:
            ctx.logger.debug(
                "%s: removing possible valid_lft and preferred_lft on %s", name, addr
            )
            replace_address(
                sock,
                addr.address,
                addr.prefixlen,
                index=link_index,
                broadcast=addr.broadcast,
            )

    # Configure IPv6 autoconf
    has_ipv6 = (
        data["int_version"] == 6
        or data["int_ipv6auto"]
        or any(alias["alias_version"] == 6 for alias in aliases)
    )
    autoconf = "1" if has_ipv6 else "0"
    ctx.middleware.call_sync(
        "tunable.set_sysctl", f"net.ipv6.conf.{name}.autoconf", autoconf
    )

    # Handle keepalived for VIPs
    if vip or alias_vips:
        if not ctx.middleware.call_sync("service.started", "keepalived"):
            ctx.middleware.call_sync(
                "service.control", "START", "keepalived"
            ).wait_sync(raise_error=True)
        else:
            ctx.middleware.call_sync(
                "service.control", "RELOAD", "keepalived"
            ).wait_sync(raise_error=True)

    # Add addresses in database but not configured
    for addr in addrs_database - addrs_configured:
        address = addr.address
        if address == vip or address in alias_vips:
            continue
        ctx.logger.debug("%s: adding %s", name, addr)
        add_address(
            sock,
            addr.address,
            addr.prefixlen,
            index=link_index,
            broadcast=addr.broadcast,
        )

    # Configure MTU (skip for bond members)
    skip_mtu = sync_data.is_bond_member(name)
    if not skip_mtu:
        if data["int_mtu"]:
            if link.mtu != data["int_mtu"]:
                set_link_mtu(sock, data["int_mtu"], index=link_index)
        elif link.mtu != 1500:
            set_link_mtu(sock, 1500, index=link_index)

    # Set interface description
    if data["int_name"]:
        try:
            set_link_alias(sock, data["int_name"], index=link_index)
        except Exception:
            ctx.logger.warning(
                "Failed to set interface description on %s", name, exc_info=True
            )

    # Bring interface up
    if not (link.flags & IFFlags.UP):
        set_link_up(sock, index=link_index)

    # Return True if DHCP should be started
    return not dhclient_run and data["int_dhcp"]
