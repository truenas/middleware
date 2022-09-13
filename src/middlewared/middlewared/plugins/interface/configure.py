import ipaddress
import os
import signal
import re
import textwrap

from .netif import netif
from .interface_types import InterfaceType
from middlewared.service import private, Service


class InterfaceService(Service):

    class Config:
        namespace_alias = 'interfaces'

    @private
    def configure(self, data, aliases, options):
        options = options or {}
        name = data['int_interface']
        self.logger.info('Configuring interface %r', name)
        iface = netif.get_interface(name)
        addrs_configured = set([a for a in iface.addresses if a.af != netif.AddressFamily.LINK])
        has_ipv6 = data['int_version'] == 6 or data['int_ipv6auto']
        if self.middleware.call_sync('failover.node') == 'B':
            addr_key = 'int_address_b'
            alias_key = 'alias_address_b'
        else:
            addr_key = 'int_address'
            alias_key = 'alias_address'

        addrs_database = set()
        dhclient_run, dhclient_pid = self.middleware.call_sync('interface.dhclient_status', name)
        if dhclient_run and not data['int_dhcp']:
            # dhclient is running on the interface but is marked to not have dhcp configure the interface
            self.logger.debug('Killing dhclient for %r', name)
            os.kill(dhclient_pid, signal.SIGTERM)
        elif dhclient_run and data['int_dhcp'] and (i := self.middleware.call_sync('interface.dhclient_leases', name)):
            # dhclient is running on the interface and is marked for dhcp AND we have a lease file for it
            _addr = re.search(r'fixed-address\s+(.+);', i)
            _net = re.search(r'option subnet-mask\s+(.+);', i)
            if (_addr and (_addr := _addr.group(1))) and (_net and (_net := _net.group(1))):
                addrs_database.add(self.alias_to_addr({'address': _addr, 'netmask': _net}))
            else:
                self.logger.info('Unable to get address from dhclient lease file for %r', name)

        if data[addr_key] and not data['int_dhcp']:
            # TODO: how are we handling int_ipv6auto (is it SLAAC or stateless DHCPv6 or stateful DHCPv6)??
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

        if has_ipv6 and not [i for i in map(str, iface.addresses) if i.startswith('fe80::')]:
            # https://tools.ietf.org/html/rfc4291#section-2.5.1
            # add an EUI64 link-local ipv6 address if one doesn't already exist
            mac = iface.link_address.replace(':', '')
            mac = mac[0:6] + 'fffe' + mac[6:]
            mac = hex(int(mac[0:2], 16) ^ 2)[2:].zfill(2) + mac[2:]
            link_local = {'address': 'fe80::' + ':'.join(textwrap.wrap(mac, 4)), 'netmask': '64'}
            addrs_database.add(self.alias_to_addr(link_local))

        for addr in addrs_configured:
            address = str(addr.address)
            if address == vip or address in alias_vips or (has_ipv6 and address.startswith('fe80::')):
                # keepalived service is responsible for deleting the VIP(s)
                # dont remove fe80 address if ipv6 is configured since it's needed
                continue
            elif addr not in addrs_database:
                # Remove addresses configured and not in database
                self.logger.debug('%s: removing %s', name, addr)
                iface.remove_address(addr)
            elif not data['int_dhcp']:
                self.logger.debug('%s: removing possible valid_lft and preferred_lft on %s', name, addr)
                iface.replace_address(addr)
            # TODO: what are we doing with ipv6auto??

        if vip or alias_vips:
            if not self.middleware.call_sync('service.started', 'keepalived'):
                self.middleware.call_sync('service.start', 'keepalived')
            else:
                self.middleware.call_sync('service.reload', 'keepalived')
            iface.vrrp_config = self.middleware.call_sync('interfaces.vrrp_config', name)

        # Add addresses in database and not configured
        for addr in (addrs_database - addrs_configured):
            address = str(addr.address)
            # keepalived service is responsible for adding the VIP(s)
            if address == vip or address in alias_vips:
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

        if netif.InterfaceFlags.UP not in iface.flags:
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
            if netif.InterfaceFlags.UP not in iface.flags:
                iface.up()
            return self.middleware.call_sync('interface.dhclient_start', iface.name, wait_dhcp)

    @private
    def unconfigure(self, iface, cloned_interfaces, parent_interfaces):
        name = iface.name
        self.logger.info('Unconfiguring interface %r', name)

        # Interface not in database lose addresses
        iface.flush()

        dhclient_running, dhclient_pid = self.middleware.call_sync('interface.dhclient_status', name)
        # Kill dhclient if its running for this interface
        if dhclient_running:
            os.kill(dhclient_pid, signal.SIGTERM)

        # If we have bridge/vlan/lagg not in the database at all
        # it gets destroy, otherwise just bring it down.
        if (name not in cloned_interfaces and
                self.middleware.call_sync('interface.type', iface.__getstate__()) in [
                    InterfaceType.BRIDGE, InterfaceType.LINK_AGGREGATION, InterfaceType.VLAN,
                ]):
            netif.destroy_interface(name)
        elif name not in parent_interfaces:
            iface.down()

    @private
    def alias_to_addr(self, alias):
        addr = netif.InterfaceAddress()
        ip = ipaddress.ip_interface(f'{alias["address"]}/{alias["netmask"]}')
        addr.af = getattr(netif.AddressFamily, 'INET6' if ip.version == 6 else 'INET')
        addr.address = ip.ip
        addr.netmask = ip.netmask
        addr.broadcast = ip.network.broadcast_address
        if 'vhid' in alias:
            addr.vhid = alias['vhid']
        return addr
