import ipaddress
import typing

from middlewared.api import api_method
from middlewared.api.current import RouteSystemRoutesItem, RouteIpv4gwReachableArgs, RouteIpv4gwReachableResult
from middlewared.plugins.network_.route_sync import sync_impl as route_sync_impl
from middlewared.service import ValidationError, Service, filterable_api_method, private
from middlewared.utils.filter_list import filter_list
from truenas_pynetif.address.constants import AddressFamily
from truenas_pynetif.address.netlink import (
    get_addresses,
    get_routes,
    netlink_route,
)


class RouteService(Service):

    class Config:
        namespace_alias = 'routes'
        cli_namespace = 'network.route'

    @filterable_api_method(item=RouteSystemRoutesItem, roles=['NETWORK_INTERFACE_READ'])
    def system_routes(self, filters, options):
        """Query IPv4 and IPv6 routes from the kernel's main routing table.

        Returns routes currently installed in the system, including static routes,
        DHCP-learned routes, and directly connected networks. The default route
        (0.0.0.0/0 or ::/0) will have both network and netmask set to all zeros.
        """
        routes = []
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
                        {
                            'network': network,
                            'netmask': netmask,
                            'gateway': route.gateway,
                            'interface': route.oif_name,
                            'flags': [],
                            'table_id': route.table,
                            'scope': route.scope,
                            'preferred_source': route.prefsrc,
                        }
                    )
        return filter_list(routes, filters, options)

    @private
    def sync(self):
        """Synchronize the kernel's default routes with the database configuration."""
        route_sync_impl(self)

    @private
    def gateway_is_reachable(self, gateway: str, ipv: typing.Literal[4, 6] = 4) -> bool:
        match ipv:
            case 4:
                FAMILY, InterfaceClass = AddressFamily.INET, ipaddress.IPv4Interface
            case 6:
                FAMILY, InterfaceClass = AddressFamily.INET6, ipaddress.IPv6Interface
            case _:
                raise ValidationError('route.gw_reachable.ipv', f'Expected 4 or 6, got {ipv}')

        gw = ipaddress.ip_address(gateway)
        with netlink_route() as sock:
            for addr in get_addresses(sock):
                if addr.family != FAMILY or addr.scope == 254:  # skip wrong family and loopback
                    continue
                if gw in InterfaceClass(f'{addr.address}/{addr.prefixlen}').network:
                    return True

        return False

    @api_method(RouteIpv4gwReachableArgs, RouteIpv4gwReachableResult, roles=['NETWORK_INTERFACE_READ'])
    def ipv4gw_reachable(self, ipv4_gateway):
        """
        Get the IPv4 gateway and verify if it is reachable by any interface.
        """
        return self.gateway_is_reachable(ipv4_gateway, ipv=4)
