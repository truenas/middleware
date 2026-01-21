import ipaddress
import re
import typing

from pyroute2.netlink.exceptions import NetlinkError

from middlewared.api import api_method
from middlewared.api.current import RouteSystemRoutesItem, RouteIpv4gwReachableArgs, RouteIpv4gwReachableResult
from middlewared.service import ValidationError, Service, filterable_api_method, private
from middlewared.utils.filter_list import filter_list
from truenas_pynetif.address.constants import AddressFamily
from truenas_pynetif.address.netlink import get_addresses, get_links, get_routes, netlink_route
from truenas_pynetif.routing import Route, RouteFlags, RoutingTable


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
    async def sync(self):
        config = await self.middleware.call('datastore.query', 'network.globalconfiguration', [], {'get': True})

        # Generate dhcpcd.conf so we can ignore routes (def gw) option
        # in case there is one explicitly set in network config
        await self.middleware.call('etc.generate', 'dhcpcd')

        ipv4_gateway = config['gc_ipv4gateway'] or None
        if not ipv4_gateway:
            interfaces = await self.middleware.call('datastore.query', 'network.interfaces')
            if interfaces:
                interfaces = [interface['int_interface'] for interface in interfaces if interface['int_dhcp']]
            else:
                ignore = tuple(await self.middleware.call('interface.internal_interfaces'))
                interfaces = list()
                with netlink_route() as sock:
                    for iface in get_links(sock):
                        if not iface.startswith(ignore):
                            interfaces.append(iface)

            for interface in interfaces:
                dhclient_running, dhclient_pid = await self.middleware.call('interface.dhclient_status', interface)
                if dhclient_running:
                    leases = await self.middleware.call('interface.dhclient_leases', interface)
                    reg_routers = re.search(r'option routers (.+);', leases or '')
                    if reg_routers:
                        # Make sure to get first route only
                        ipv4_gateway = reg_routers.group(1).split(' ')[0]
                        break

        routing_table = RoutingTable()
        if ipv4_gateway:
            ipv4_gateway = Route('0.0.0.0', '0.0.0.0', ipaddress.ip_address(str(ipv4_gateway)))
            ipv4_gateway.flags.add(RouteFlags.STATIC)
            ipv4_gateway.flags.add(RouteFlags.GATEWAY)
            # If there is a gateway but there is none configured, add it
            # Otherwise change it
            if not routing_table.default_route_ipv4:
                self.logger.info('Adding IPv4 default route to {}'.format(ipv4_gateway.gateway))
                try:
                    routing_table.add(ipv4_gateway)
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
                    gw = ipv4_gateway.asdict()['gateway']
                    self.logger.error('Failed adding %s as default gateway: %r', gw, e)
            elif ipv4_gateway != routing_table.default_route_ipv4:
                _from = routing_table.default_route_ipv4.gateway
                _to = ipv4_gateway.gateway
                self.logger.info(f'Changing IPv4 default route from {_from} to {_to}')
                routing_table.change(ipv4_gateway)
        elif routing_table.default_route_ipv4:
            # If there is no gateway in database but one is configured
            # remove it
            self.logger.info('Removing IPv4 default route')
            routing_table.delete(routing_table.default_route_ipv4)

        ipv6_gateway = config['gc_ipv6gateway'] or None
        if ipv6_gateway:
            if ipv6_gateway.count("%") == 1:
                ipv6_gateway, ipv6_gateway_interface = ipv6_gateway.split("%")
            else:
                ipv6_gateway_interface = None
            ipv6_gateway = Route('::', '::', ipaddress.ip_address(str(ipv6_gateway)), ipv6_gateway_interface)
            ipv6_gateway.flags.add(RouteFlags.STATIC)
            ipv6_gateway.flags.add(RouteFlags.GATEWAY)
            # If there is a gateway but there is none configured, add it
            # Otherwise change it
            if not routing_table.default_route_ipv6:
                self.logger.info(f'Adding IPv6 default route to {ipv6_gateway.gateway}')
                routing_table.add(ipv6_gateway)
            elif ipv6_gateway != routing_table.default_route_ipv6:
                _from = routing_table.default_route_ipv6.gateway
                _to = ipv6_gateway.gateway
                self.logger.info(f'Changing IPv6 default route from {_from} to {_to}')
                routing_table.change(ipv6_gateway)
        elif routing_table.default_route_ipv6:
            # If there is no gateway in database but one is configured
            # remove it
            interface = routing_table.default_route_ipv6.interface
            autoconfigured_interface = await self.middleware.call(
                'datastore.query', 'network.interfaces', [
                    ['int_interface', '=', interface],
                    ['int_ipv6auto', '=', True],
                ]
            )
            if not autoconfigured_interface:
                self.logger.info('Removing IPv6 default route as there is no IPv6 autoconfiguration')
                routing_table.delete(routing_table.default_route_ipv6)

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
