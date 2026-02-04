import ipaddress
import re

from middlewared.service import private, Service
from truenas_pynetif.address.constants import AddressFamily
from truenas_pynetif.address.netlink import get_link_addresses, netlink_route
from truenas_pynetif.bits import InterfaceFlags
from truenas_pynetif.netif import destroy_interface, get_interface
from truenas_pynetif.netlink import AddressInfo

from .bond import configure_bond_impl, configure_bonds_impl
from .interface_types import InterfaceType


class InterfaceService(Service):

    class Config:
        namespace_alias = 'interfaces'

    @private
    def __addrs_configured(self, name):
        ac = set()
        with netlink_route() as sock:
            for addr in get_link_addresses(sock, name):
                if addr.family != AddressFamily.LINK:
                    ac.add(addr)
        return ac

    @private
    def configure(self, data, aliases, options):
        options = options or {}
        name = data['int_interface']
        self.logger.info('Configuring interface %r', name)
        addrs_configured = self.__addrs_configured(name)
        has_ipv6 = (
            data['int_version'] == 6 or
            data['int_ipv6auto'] or
            any(alias['alias_version'] == 6 for alias in aliases)
        )
        if self.middleware.call_sync('failover.node') == 'B':
            addr_key = 'int_address_b'
            alias_key = 'alias_address_b'
        else:
            addr_key = 'int_address'
            alias_key = 'alias_address'

        addrs_database = set()
        dhclient_run, dhclient_pid = self.middleware.call_sync('interface.dhclient_status', name)
        if dhclient_run and not data['int_dhcp']:
            # DHCP is running on the interface but is marked to not have dhcp configure the interface
            self.logger.debug('Stopping DHCP for %r', name)
            self.middleware.call_sync('interface.dhcp_stop', name)
        elif dhclient_run and data['int_dhcp'] and (i := self.middleware.call_sync('interface.dhclient_leases', name)):
            # dhclient is running on the interface and is marked for dhcp AND we have a lease file for it
            _addr = re.search(r'fixed-address\s+(.+);', i)
            _net = re.search(r'option subnet-mask\s+(.+);', i)
            if (_addr and (_addr := _addr.group(1))) and (_net and (_net := _net.group(1))):
                addrs_database.add(self.alias_to_addr({'address': _addr, 'netmask': _net}))
            else:
                self.logger.info('Unable to get address from dhclient lease file for %r', name)

        if data[addr_key] and not data['int_dhcp']:
            addrs_database.add(self.alias_to_addr({'address': data[addr_key], 'netmask': data['int_netmask']}))

        if vip := data.get('int_vip', ''):
            netmask = '32' if data['int_version'] == 4 else '128'
            addrs_database.add(self.alias_to_addr({'address': vip, 'netmask': netmask}))

        alias_vips = []
        for alias in aliases:
            addrs_database.add(self.alias_to_addr({'address': alias[alias_key], 'netmask': alias['alias_netmask']}))
            if alias['alias_vip']:
                alias_vip = alias['alias_vip']
                alias_vips.append(alias_vip)
                addrs_database.add(self.alias_to_addr(
                    {'address': alias_vip, 'netmask': '32' if alias['alias_version'] == 4 else '128'}
                ))

        iface = get_interface(name)
        for addr in addrs_configured:
            address = addr.address
            if address.startswith('fe80::'):
                # having a link-local address causes no harm and is a
                # pre-requisite for IPv6 working in general. Just ignore it.
                continue
            elif address == vip or address in alias_vips:
                # keepalived service is responsible for deleting the VIP(s)
                continue
            elif addr not in addrs_database:
                # Remove addresses configured and not in database
                self.logger.debug('%s: removing %s', name, addr)
                iface.remove_address(addr)
            elif not data['int_dhcp']:
                self.logger.debug('%s: removing possible valid_lft and preferred_lft on %s', name, addr)
                iface.replace_address(addr)

        autoconf = '1' if has_ipv6 else '0'
        self.middleware.call_sync('tunable.set_sysctl', f'net.ipv6.conf.{name}.autoconf', autoconf)

        if vip or alias_vips:
            if not self.middleware.call_sync('service.started', 'keepalived'):
                self.middleware.call_sync('service.control', 'START', 'keepalived').wait_sync(raise_error=True)
            else:
                self.middleware.call_sync('service.control', 'RELOAD', 'keepalived').wait_sync(raise_error=True)

        # Add addresses in database and not configured
        for addr in (addrs_database - addrs_configured):
            address = addr.address
            if address == vip or address in alias_vips:
                # keepalived service is responsible for adding the VIP(s)
                continue
            self.logger.debug('%s: adding %s', name, addr)
            iface.add_address(addr)

        # In case there is no MTU in interface and it is currently
        # different than the default of 1500, revert it
        if not options.get('skip_mtu'):
            if data['int_mtu']:
                if iface.mtu != data['int_mtu']:
                    iface.mtu = data['int_mtu']
            elif iface.mtu != 1500:
                iface.mtu = 1500

        if data['int_name'] and iface.description != data['int_name']:
            try:
                iface.description = data['int_name']
            except Exception:
                self.logger.warning('Failed to set interface description on %s', name, exc_info=True)

        if InterfaceFlags.UP not in iface.flags:
            iface.up()

        # If dhclient is not running and dhcp is configured, the caller should
        # start it based on what we return here
        # TODO: what are we doing with ipv6auto??
        return not dhclient_run and data['int_dhcp']

    @private
    def autoconfigure(self, iface, wait_dhcp):
        dhclient_running = self.middleware.call_sync('interface.dhclient_status', iface.name)[0]
        if not dhclient_running:
            # Make sure interface is UP before starting dhclient
            # NAS-103577
            if InterfaceFlags.UP not in iface.flags:
                iface.up()
            return self.middleware.call_sync('interface.dhclient_start', iface.name, wait_dhcp)

    @private
    def unconfigure(self, iface, cloned_interfaces, parent_interfaces):
        name = iface.name
        self.logger.info('Unconfiguring interface %r', name)

        # Interface not in database lose addresses
        iface.flush()

        dhclient_running, dhclient_pid = self.middleware.call_sync('interface.dhclient_status', name)
        # Stop DHCP if it's running for this interface
        if dhclient_running:
            # Use dhcp_stop for proper cleanup with dhcpcd
            self.middleware.call_sync('interface.dhcp_stop', name)

        # If we have bridge/vlan/lagg not in the database at all
        # it gets destroy, otherwise just bring it down.
        if (name not in cloned_interfaces and
                self.middleware.call_sync('interface.type', iface.asdict()) in [
                    InterfaceType.BRIDGE, InterfaceType.LINK_AGGREGATION, InterfaceType.VLAN,
                ]):
            destroy_interface(name)
        elif name not in parent_interfaces:
            iface.down()

    @private
    def alias_to_addr(self, alias):
        # NOTE: 'vhid' is a legacy CARP property kept in the database to reduce churn.
        # It is not used - VIPs are now managed by keepalived.
        return self.interface_to_addr(ipaddress.ip_interface(f'{alias["address"]}/{alias["netmask"]}'))

    @private
    def interface_to_addr(self, ip):
        return AddressInfo(
            family=AddressFamily.INET6 if ip.version == 6 else AddressFamily.INET,
            prefixlen=ip.network.prefixlen,
            address=str(ip.ip),
            broadcast=str(ip.network.broadcast_address),
        )

    @private
    async def get_configured_interfaces(self):
        """
        Return a list of configured interfaces.

        This will include names of regular interfaces that have been configured,
        plus any higher-order interfaces and their constituents."""
        ds = await self.middleware.call('interface.get_datastores')
        # Interfaces
        result = set([i['int_interface'] for i in ds['interfaces']])
        # Bridges
        for bridge in ds['bridge']:
            result.update(bridge['members'])
        # VLAN
        for vlan in ds['vlan']:
            result.add(vlan['vlan_pint'])
        # Link Aggregation
        for lag in ds['laggmembers']:
            result.add(lag['lagg_physnic'])
        return list(result)

    @private
    def configure_bonds(self, sock, parent_interfaces, sync_interface_opts):
        """Configure all bond interfaces from database."""
        return configure_bonds_impl(self.context, sock, parent_interfaces, sync_interface_opts)

    @private
    def configure_bond(self, sock, lagg, members, parent_interfaces, sync_interface_opts):
        """Configure a single bond interface."""
        return configure_bond_impl(self.context, sock, lagg, members, parent_interfaces, sync_interface_opts)
