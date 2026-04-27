from __future__ import annotations

import ipaddress
import os
import socket

from truenas_pynetif.address.address import add_address, remove_address, replace_address
from truenas_pynetif.address.constants import AddressFamily, IFFlags
from truenas_pynetif.address.get_ipaddresses import get_link_addresses
from truenas_pynetif.address.link import set_link_alias, set_link_mtu, set_link_up
from truenas_pynetif.ethtool import DeviceNotFound, get_ethtool, OperationNotSupported
from truenas_pynetif.netlink import AddressDoesNotExist, AddressInfo, LinkInfo

from middlewared.plugins.interface.dhcp import dhcp_leases, dhcp_status, dhcp_stop
from middlewared.service import ServiceContext
from middlewared.utils.interface import NETIF_COMPLETE_SENTINEL

from .sync_data import SyncData

__all__ = ("configure_addresses_impl",)


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
    # Order matters: when multiple IPv4s share a subnet, the kernel marks the
    # FIRST added as primary and pins the subnet's connected-route src to it
    # (which drives default-gateway source selection). Use a dict (insertion-
    # ordered) as an ordered set so the add path below is deterministic --
    # iterating a regular set does not guarantee order.
    addrs_database: dict[AddressInfo, None] = {}

    # Check DHCP status
    status = dhcp_status(name)
    if status.running and not data["int_dhcp"]:
        ctx.logger.debug("Stopping DHCP for %r", name)
        ctx.middleware.run_coroutine(dhcp_stop(name))
    elif status.running and data["int_dhcp"]:
        lease = dhcp_leases(name)
        if lease and lease.ip_address and lease.subnet_mask:
            addrs_database.setdefault(
                _alias_to_addr(
                    {
                        "address": lease.ip_address,
                        "netmask": lease.subnet_mask,
                    }
                )
            )
        else:
            ctx.logger.info("Unable to get address from dhcpcd lease for %r", name)

    # Add primary address from database
    if data[addr_key] and not data["int_dhcp"]:
        addrs_database.setdefault(
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
        addrs_database.setdefault(_alias_to_addr({"address": vip, "netmask": netmask}))

    # Add alias addresses
    alias_vips = []
    for alias in aliases:
        addrs_database.setdefault(
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
            addrs_database.setdefault(
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
            ctx.logger.debug("%s: removing %s", name, addr.address)
            try:
                remove_address(sock, addr.address, addr.prefixlen, index=link_index)
            except AddressDoesNotExist:
                # addresses not existing at this point could
                # be because of dhcpcd being stopped which
                # removes the ips but also because of any
                # other myriad of reasons. Just ignore it
                pass
            except Exception as e:
                ctx.logger.debug(
                    "%s: unexpected error removing %s: %e", name, addr.address, e
                )

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
    ctx.call_sync2(ctx.s.tunable.set_sysctl, f"net.ipv6.conf.{name}.autoconf", autoconf)

    # Add addresses in database but not configured. Iterate the dict in
    # insertion order so int_address is added first and becomes the kernel
    # primary for its subnet (see comment at the addrs_database declaration).
    for addr in addrs_database:
        if addr in addrs_configured:
            continue
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

    # Bring interface up
    if not (link.flags & IFFlags.UP):
        set_link_up(sock, index=link_index)

    # Handle keepalived for VIPs.  Skip the START during early boot (when called
    # from ix-netif.service) because keepalived requires network-online.target
    # which cannot be reached until ix-netif.service itself completes — starting
    # it here would deadlock for 95s.  The sentinel is written by ix-netif.service
    # on successful completion, so its presence means the network is up.
    if vip or alias_vips:
        if ctx.middleware.call_sync("service.started", "keepalived"):
            ctx.middleware.call_sync(
                "service.control", "RELOAD", "keepalived"
            ).wait_sync(raise_error=True)
        elif os.path.exists(NETIF_COMPLETE_SENTINEL):
            ctx.middleware.call_sync(
                "service.control", "START", "keepalived"
            ).wait_sync(raise_error=True)
        # else: early boot call from ix-netif.service; keepalived will be
        # started later once network-online.target is satisfied.

    # Configure MTU (skip for bond members)
    skip_mtu = sync_data.is_bond_member(name)
    if not skip_mtu:
        if data["int_mtu"]:
            if link.mtu != data["int_mtu"]:
                set_link_mtu(sock, data["int_mtu"], index=link_index)
        elif link.mtu != 1500:
            set_link_mtu(sock, 1500, index=link_index)

    # Apply FEC mode (physical interfaces only; virtual interfaces never have int_fec_mode set)
    if fec_mode := data.get("int_fec_mode"):
        try:
            get_ethtool().set_fec(name, fec_mode)
        except (OperationNotSupported, DeviceNotFound):
            pass
        except Exception:
            ctx.logger.warning("Failed to set FEC mode on %s", name, exc_info=True)

    # Set interface description
    if data["int_name"]:
        try:
            set_link_alias(sock, data["int_name"], index=link_index)
        except Exception:
            ctx.logger.warning(
                "Failed to set interface description on %s", name, exc_info=True
            )

    # Return True if DHCP should be started
    return not status.running and data["int_dhcp"]
