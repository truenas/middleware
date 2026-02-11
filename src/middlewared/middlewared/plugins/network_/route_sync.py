import re
import socket

from middlewared.service import ServiceContext

from truenas_pynetif.address.constants import AddressFamily
from truenas_pynetif.address.netlink import (
    add_route,
    change_route,
    delete_route,
    get_default_route,
    get_links,
    netlink_route,
)
from truenas_pynetif.netlink import NetlinkError

__all__ = ("sync_impl",)


def _get_default_ip4_route_from_dhcpcd(
    ctx: ServiceContext, sock: socket.socket
) -> str | None:
    ifaces = ctx.middleware.call_sync("datastore.query", "network.interfaces")
    if ifaces:
        ifaces = [i["int_interface"] for i in ifaces if i["int_dhcp"]]
    else:
        ignore = tuple(ctx.middleware.call_sync("interface.internal_interfaces"))
        ifaces = list()
        for iface in get_links(sock):
            if not iface.startswith(ignore):
                ifaces.append(iface)

    for i in ifaces:
        dhclient_running, dhclient_pid = ctx.middleware.call_sync(
            "interface.dhclient_status", i
        )
        if dhclient_running:
            leases = ctx.middleware.call_sync("interface.dhclient_leases", i)
            reg_routers = re.search(r"option routers (.+);", leases or "")
            if reg_routers:
                # Make sure to get first route only
                return reg_routers.group(1).split(" ")[0]
    return None


def _sync_ip4_impl(ctx: ServiceContext, sock: socket.socket, dbgw: str | None):
    cur_gw = get_default_route(sock, family=AddressFamily.INET)
    if not dbgw:
        # no gateway specified in db, so let's see if one
        # is installed via dhcpcd on any of the interfaces
        dbgw = _get_default_ip4_route_from_dhcpcd(ctx, sock)

    if dbgw:
        if not cur_gw:
            # there is a gateway in our database (dbgw) but
            # we don't currently have one installed in OS (cur_gw)
            # so we'll add it
            ctx.logger.info("Adding IPv4 default route to %s", dbgw)
            try:
                add_route(sock, gateway=dbgw)
            except NetlinkError as e:
                # Error could be (101, Network host unreachable)
                # This error occurs in random race conditions.
                # For example, can occur in the following scenario:
                #   1. delete all configured interfaces on system
                #   2. interface.sync() gets called and starts dhcp
                #       on all interfaces detected on the system
                #   3. route.sync() gets called which eventually
                #       calls dhclient_leases which reads a file on
                #       disk to see if we have any previously
                #       defined default gateways from DHCP.
                #       However, by the time we read this file,
                #       DHCP could still be requesting an
                #       address from the DHCP server
                #   4. so when we try to install our own default
                #       gateway manually (even though DHCP will
                #       do this for us) it will fail expectedly here.
                # Either way, let's log the error.
                ctx.logger.error("Failed adding %s as default gateway: %r", dbgw, e)
        elif cur_gw.gateway != dbgw:
            # there is a gateway installed in OS (cur_gw) but
            # it doesn't match what the gateway is in our db
            # so we'll change it
            ctx.logger.info(
                "Changing IPv4 default route from %s to %s",
                cur_gw.gateway,
                dbgw,
            )
            change_route(sock, gateway=dbgw)
    elif cur_gw:
        # there is no gateway in the database but there is
        # one installed in the OS so we'll remove it
        ctx.logger.info("Removing IPv4 default route: %s", cur_gw.gateway)
        delete_route(sock, gateway=cur_gw.gateway)


def _sync_ip6_impl(ctx: ServiceContext, sock: socket.socket, dbgw: str | None):
    cur_gw = get_default_route(sock, family=AddressFamily.INET6)
    dbgw_iface = None
    if dbgw and dbgw.count("%") == 1:
        dbgw, dbgw_iface = dbgw.split("%")

    if dbgw:
        if not cur_gw:
            # there is a gateway in our database (dbgw) but
            # we don't currently have one installed in OS (cur_gw)
            # so we'll add it
            ctx.logger.info("Adding IPv6 default route to %s", dbgw)
            add_route(sock, gateway=dbgw, name=dbgw_iface)
        elif cur_gw.gateway != dbgw:
            # there is a gateway installed in OS (cur_gw) but
            # it doesn't match what the gateway is in our db
            # so we'll change it
            ctx.logger.info(
                "Changing IPv6 default route from %s to %s",
                cur_gw.gateway,
                dbgw,
            )
            change_route(sock, gateway=dbgw, name=dbgw_iface)
    elif cur_gw:
        # there is no gateway in the database but there is
        # one installed in the OS. If we do not have any
        # interface with ipv6 SLAAC enabled, then we'll
        # remove the route.
        if not ctx.middleware.call_sync(
            "datastore.query",
            "network.interfaces",
            [
                ["int_interface", "=", cur_gw.oif_name],
                ["int_ipv6auto", "=", True],
            ],
        ):
            ctx.logger.info("Removing IPv6 default route: %s", cur_gw.gateway)
            delete_route(sock, gateway=cur_gw.gateway, index=cur_gw.oif)


def sync_impl(ctx: ServiceContext):
    # Generate dhcpcd.conf so we can ignore routes (def gw) option
    # in case there is one explicitly set in network config
    ctx.middleware.call_sync("etc.generate", "dhcpcd")
    config = ctx.middleware.call_sync(
        "datastore.query", "network.globalconfiguration", [], {"get": True}
    )
    with netlink_route() as sock:
        _sync_ip4_impl(ctx, sock, config["gc_ipv4gateway"])
        _sync_ip6_impl(ctx, sock, config["gc_ipv6gateway"])
