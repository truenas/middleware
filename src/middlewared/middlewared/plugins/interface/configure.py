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

        addrs_database = set()
        addrs_configured = set([
            a for a in iface.addresses
            if a.af != netif.AddressFamily.LINK
        ])

        has_ipv6 = data['int_ipv6auto'] or False

        if (
            self.middleware.call_sync('system.is_enterprise') and self.middleware.call_sync('failover.node') == 'B'
        ):
            ipv4_field = 'int_ipv4address_b'
            ipv6_field = 'int_ipv6address_b'
            alias_field = 'alias_address_b'
        elif (
            # Bridge interface members should not have IP addresses
            self.middleware.call_sync('interface.type', iface.__getstate__()) in [
                InterfaceType.BRIDGE,
                ]):
            self.logger.info('%r is bridge member, handle specially')
            # TODO: Specially handle bridge member interfaces: ip change should go to DB, but NOT live.
            # TODO: signal to web UI that this change is not live, so config can be preemptively changed
            ipv4_field = 'int_ipv4address'
            ipv6_field = 'int_ipv6address'
            alias_field = 'alias_address'
        else:
            ipv4_field = 'int_ipv4address'
            ipv6_field = 'int_ipv6address'
            alias_field = 'alias_address'
        dhclient_running, dhclient_pid = self.middleware.call_sync('interface.dhclient_status', name)
        if dhclient_running and data['int_dhcp']:
            leases = self.middleware.call_sync('interface.dhclient_leases', name)
            if leases:
                reg_address = re.search(r'fixed-address\s+(.+);', leases)
                reg_netmask = re.search(r'option subnet-mask\s+(.+);', leases)
                if reg_address and reg_netmask:
                    addrs_database.add(self.alias_to_addr({
                        'address': reg_address.group(1),
                        'netmask': reg_netmask.group(1),
                    }))
                else:
                    self.logger.info('Unable to get address from dhclient')
            if data[ipv6_field] and not has_ipv6:
                addrs_database.add(self.alias_to_addr({
                    'address': data[ipv6_field],
                    'netmask': data['int_v6netmaskbit'],
                }))
                has_ipv6 = True
        else:
            if data[ipv4_field] and not data['int_dhcp']:
                addrs_database.add(self.alias_to_addr({
                    'address': data[ipv4_field],
                    'netmask': data['int_v4netmaskbit'],
                }))
            if data[ipv6_field] and not has_ipv6:
                addrs_database.add(self.alias_to_addr({
                    'address': data[ipv6_field],
                    'netmask': data['int_v6netmaskbit'],
                }))
                has_ipv6 = True

        # configure VRRP
        vip = data.get('int_vip', '')
        if vip:
            addrs_database.add(self.alias_to_addr({
                'address': vip,
                'netmask': '32',
            }))

        vipv6 = data.get('int_vipv6address', '')
        if vipv6:
            addrs_database.add(self.alias_to_addr({
                'address': vipv6,
                'netmask': '128',
            }))

        alias_vips = []
        for alias in aliases:
            if alias[alias_field]:
                addrs_database.add(self.alias_to_addr({
                    'address': alias[alias_field],
                    'netmask': alias['alias_netmask'],
                }))

            if alias['alias_vip']:
                alias_vip = alias['alias_vip']
                alias_vips.append(alias_vip)
                addrs_database.add(self.alias_to_addr({
                    'address': alias_vip,
                    'netmask': '32' if alias['alias_version'] == 4 else '128',
                }))

        if has_ipv6 and not [i for i in map(str, iface.addresses) if i.startswith('fe80::')]:
            # https://tools.ietf.org/html/rfc4291#section-2.5.1
            # add an EUI64 link-local ipv6 address if one doesn't already exist
            mac = iface.link_address.address.address.replace(':', '')
            mac = mac[0:6] + 'fffe' + mac[6:]
            mac = hex(int(mac[0:2], 16) ^ 2)[2:].zfill(2) + mac[2:]
            link_local = {
                'address': 'fe80::' + ':'.join(textwrap.wrap(mac, 4)),
                'netmask': '64',
            }
            addrs_database.add(self.alias_to_addr(link_local))

        if dhclient_running and not data['int_dhcp']:
            self.logger.debug('Killing dhclient for {}'.format(name))
            os.kill(dhclient_pid, signal.SIGTERM)

        # Remove addresses configured and not in database
        for addr in addrs_configured:
            address = str(addr.address)
            # keepalived service is responsible for deleting the VIP(s)
            if address in (vip, vipv6) or address in alias_vips:
                continue
            if vipv6 and address.startswith('fe80::'):
                continue
            if addr not in addrs_database:
                self.logger.debug('{}: removing {}'.format(name, addr))
                iface.remove_address(addr)
            elif not data['int_dhcp']:
                self.logger.debug('{}: removing possible valid_lft and preferred_lft on {}'.format(name, addr))
                iface.replace_address(addr)

        if vip or vipv6 or alias_vips:
            if not self.middleware.call_sync('service.started', 'keepalived'):
                self.middleware.call_sync('service.start', 'keepalived')
            else:
                self.middleware.call_sync('service.reload', 'keepalived')
            iface.vrrp_config = self.middleware.call_sync('interfaces.vrrp_config', name)

        # Add addresses in database and not configured
        for addr in (addrs_database - addrs_configured):
            address = str(addr.address)
            # keepalived service is responsible for adding the VIP(s)
            if address in (vip, vipv6) or address in alias_vips:
                continue
            self.logger.debug('{}: adding {}'.format(name, addr))
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
                self.logger.warn(f'Failed to set interface {name} description', exc_info=True)

        if netif.InterfaceFlags.UP not in iface.flags:
            iface.up()

        # If dhclient is not running and dhcp is configured, lets start it
        return not dhclient_running and data['int_dhcp']

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
