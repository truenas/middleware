import re
import ipaddress
import os
import contextlib
import signal
import asyncio
import typing

from pyroute2.netlink.exceptions import NetlinkError

from middlewared.api import api_method
from middlewared.api.current import RouteSystemRoutesItem, RouteIpv4gwReachableArgs, RouteIpv4gwReachableResult
from middlewared.service import ValidationError, Service, filterable_api_method, private
from middlewared.plugins.interface.netif import netif
from middlewared.utils import filter_list

RE_RTSOLD_INTERFACE = re.compile(r'Interface (.+)')
RE_RTSOLD_NUMBER_OF_VALID_RAS = re.compile(r'number of valid RAs: ([0-9]+)')


class RouteService(Service):

    class Config:
        namespace_alias = 'routes'
        cli_namespace = 'network.route'

    @filterable_api_method(item=RouteSystemRoutesItem, roles=['NETWORK_INTERFACE_READ'])
    def system_routes(self, filters, options):
        """
        Get current/applied network routes.
        """
        rtable = netif.RoutingTable()
        return filter_list([r.asdict() for r in rtable.routes], filters, options)

    @private
    async def configured_default_ipv4_route(self):
        route = netif.RoutingTable().default_route_ipv4
        return bool(route or (await self.middleware.call('network.configuration.config'))['ipv4gateway'])

    @private
    async def sync(self):
        config = await self.middleware.call('datastore.query', 'network.globalconfiguration', [], {'get': True})

        # Generate dhclient.conf so we can ignore routes (def gw) option
        # in case there is one explicitly set in network config
        await self.middleware.call('etc.generate', 'dhclient')

        ipv4_gateway = config['gc_ipv4gateway'] or None
        if not ipv4_gateway:
            interfaces = await self.middleware.call('datastore.query', 'network.interfaces')
            if interfaces:
                interfaces = [interface['int_interface'] for interface in interfaces if interface['int_dhcp']]
            else:
                ignore = tuple(await self.middleware.call('interface.internal_interfaces'))
                interfaces = list()
                for iface in netif.get_address_netlink().get_links():
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

        routing_table = netif.RoutingTable()
        if ipv4_gateway:
            ipv4_gateway = netif.Route('0.0.0.0', '0.0.0.0', ipaddress.ip_address(str(ipv4_gateway)))
            ipv4_gateway.flags.add(netif.RouteFlags.STATIC)
            ipv4_gateway.flags.add(netif.RouteFlags.GATEWAY)
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
                    #       defined default gateways from dhclient.
                    #       However, by the time we read this file,
                    #       dhclient could still be requesting an
                    #       address from the DHCP server
                    #   4. so when we try to install our own default
                    #       gateway manually (even though dhclient will
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
            ipv6_gateway = netif.Route('::', '::', ipaddress.ip_address(str(ipv6_gateway)), ipv6_gateway_interface)
            ipv6_gateway.flags.add(netif.RouteFlags.STATIC)
            ipv6_gateway.flags.add(netif.RouteFlags.GATEWAY)
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
            remove = False
            if not autoconfigured_interface:
                self.logger.info('Removing IPv6 default route as there is no IPv6 autoconfiguration')
                remove = True
            elif not await self.middleware.call('route.has_valid_router_announcements', interface):
                self.logger.info('Removing IPv6 default route as IPv6 autoconfiguration has not succeeded')
                remove = True
            if remove:
                routing_table.delete(routing_table.default_route_ipv6)

    @private
    def gateway_is_reachable(self, gateway: str, ipv: typing.Literal[4, 6] = 4) -> bool:
        match ipv:
            case 4:
                FAMILY, InterfaceClass = netif.AddressFamily.INET, ipaddress.IPv4Interface
            case 6:
                FAMILY, InterfaceClass = netif.AddressFamily.INET6, ipaddress.IPv6Interface
            case _:
                raise ValidationError('route.gw_reachable.ipv', f'Expected 4 or 6, got {ipv}')

        gw = ipaddress.ip_address(gateway)
        for addr in netif.get_address_netlink().get_addresses():
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

    @private
    async def has_valid_router_announcements(self, interface):
        rtsold_dump_path = '/var/run/rtsold.dump'

        try:
            with open('/var/run/rtsold.pid') as f:
                rtsold_pid = int(f.read().strip())
        except (FileNotFoundError, ValueError):
            self.logger.warning('rtsold pid file does not exist')
            return False

        with contextlib.suppress(FileNotFoundError):
            os.unlink(rtsold_dump_path)

        try:
            os.kill(rtsold_pid, signal.SIGUSR1)
        except ProcessLookupError:
            self.logger.warning('rtsold is not running')
            return False

        for i in range(10):
            await asyncio.sleep(0.2)
            try:
                with open(rtsold_dump_path) as f:
                    dump = f.readlines()
                    break
            except FileNotFoundError:
                continue
        else:
            self.logger.warning('rtsold has not dumped status')
            return False

        current_interface = None
        for line in dump:
            line = line.strip()

            m = RE_RTSOLD_INTERFACE.match(line)
            if m:
                current_interface = m.group(1)

            if current_interface == interface:
                m = RE_RTSOLD_NUMBER_OF_VALID_RAS.match(line)
                if m:
                    return int(m.group(1)) > 0

        self.logger.warning('Have not found %s status in rtsold dump', interface)
        return False
