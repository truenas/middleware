import ipaddress
from typing import Any, Literal

from truenas_pynetif.address.constants import AddressFamily
from truenas_pynetif.address.netlink import (
    get_addresses,
    get_routes,
    netlink_route,
)

from middlewared.api.current import QueryOptions, RouteSystemRoutesItem
from middlewared.service_exception import ValidationError
from middlewared.utils.filter_list import filter_list

__all__ = ("get_system_routes", "gateway_is_reachable")


def get_system_routes(
    filters: list[Any], options: QueryOptions
) -> list[RouteSystemRoutesItem] | RouteSystemRoutesItem | int:
    """Query IPv4 and IPv6 routes from the kernel's main routing table."""
    routes: list[RouteSystemRoutesItem] = []
    with netlink_route() as sock:
        for route in get_routes(sock):
            network, netmask = None, None
            if route.family == AddressFamily.INET:
                if route.dst is None:
                    network = "0.0.0.0"
                    netmask = "0.0.0.0"
                else:
                    network = route.dst
                    netmask = str(ipaddress.IPv4Network(f"0.0.0.0/{route.dst_len}").netmask)
            elif route.family == AddressFamily.INET6:
                if route.dst is None:
                    network = "::"
                    netmask = "::"
                else:
                    network = route.dst
                    netmask = str(ipaddress.IPv6Network(f"::/{route.dst_len}").netmask)

            if network is not None and netmask is not None:
                routes.append(
                    RouteSystemRoutesItem(
                        network=network,
                        netmask=netmask,
                        gateway=route.gateway,
                        interface=route.oif_name,
                        flags=[],
                        table_id=route.table,
                        scope=route.scope,
                        preferred_source=route.prefsrc,
                    )
                )

    return filter_list(routes, filters, options, RouteSystemRoutesItem)


def gateway_is_reachable(gateway: str, ipv: Literal[4, 6] = 4) -> bool:
    """Verify whether a gateway is reachable by any configured interface."""
    family: AddressFamily
    interface_class: type[ipaddress.IPv4Interface] | type[ipaddress.IPv6Interface]
    match ipv:
        case 4:
            family, interface_class = AddressFamily.INET, ipaddress.IPv4Interface
        case 6:
            family, interface_class = AddressFamily.INET6, ipaddress.IPv6Interface
        case _:
            raise ValidationError("route.gw_reachable.ipv", f"Expected 4 or 6, got {ipv}")

    gw = ipaddress.ip_address(gateway)
    with netlink_route() as sock:
        for addr in get_addresses(sock):
            if addr.family != family or addr.scope == 254:  # skip wrong family and loopback
                continue
            if gw in interface_class(f"{addr.address}/{addr.prefixlen}").network:
                return True

    return False
