import ipaddress
import os
import shlex
import signal
import subprocess
import re
import textwrap

from .netif import netif
from .type_base import InterfaceType

from middlewared.service import private, Service
from middlewared.utils import osc


class InterfaceService(Service):

    class Config:
        namespace_alias = 'interfaces'

    @private
    def configure(self, data, aliases, options):
        options = options or {}

        name = data['int_interface']

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
            alias_ipv4_field = 'alias_v4address_b'
            alias_ipv6_field = 'alias_v6address_b'
        else:
            ipv4_field = 'int_ipv4address'
            ipv6_field = 'int_ipv6address'
            alias_ipv4_field = 'alias_v4address'
            alias_ipv6_field = 'alias_v6address'

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

        # configure CARP/VRRP
        has_vip = data.get('int_vip', '')
        if has_vip:
            vip_data = {
                'address': data['int_vip'],
                'netmask': '32',
            }

        has_vipv6 = data.get('int_vipv6address', '')
        if has_vipv6:
            vip_data = {
                'address': data['int_vipv6address'],
                'netmask': '128',
            }

        if has_vip or has_vipv6:
            # linux doesn't use `carp_vhid` or `carp_pass` attributes
            if osc.IS_FREEBSD:
                carp_vhid = data.get('int_vhid', None)
                carp_pass = data.get('int_pass', None)

                vip_data['vhid'] = carp_vhid

                if carp_vhid:
                    advskew = None
                    for cc in iface.carp_config:
                        if cc.vhid == carp_vhid:
                            advskew = cc.advskew
                        break

            addrs_database.add(self.alias_to_addr(vip_data))

        for alias in aliases:
            if alias[alias_ipv4_field]:
                addrs_database.add(self.alias_to_addr({
                    'address': alias[alias_ipv4_field],
                    'netmask': alias['alias_v4netmaskbit'],
                }))
            if alias[alias_ipv6_field]:
                addrs_database.add(self.alias_to_addr({
                    'address': alias[alias_ipv6_field],
                    'netmask': alias['alias_v6netmaskbit'],
                }))

            if alias['alias_vip']:
                alias_vip_data = {
                    'address': alias['alias_vip'],
                    'netmask': '32',
                }

            if alias['alias_vipv6address']:
                alias_vip_data = {
                    'address': alias['alias_vipv6address'],
                    'netmask': '128',
                }

            if alias['alias_vip'] or alias['alias_vipv6address']:
                if osc.IS_FREEBSD:
                    alias_vip_data['vhid'] = data['int_vhid']

                addrs_database.add(self.alias_to_addr(alias_vip_data))

        if osc.IS_FREEBSD:
            if has_ipv6:
                iface.nd6_flags = iface.nd6_flags - {netif.NeighborDiscoveryFlags.IFDISABLED}
                iface.nd6_flags = iface.nd6_flags | {netif.NeighborDiscoveryFlags.AUTO_LINKLOCAL}
            else:
                iface.nd6_flags = iface.nd6_flags | {netif.NeighborDiscoveryFlags.IFDISABLED}
                iface.nd6_flags = iface.nd6_flags - {netif.NeighborDiscoveryFlags.AUTO_LINKLOCAL}
        else:
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
            # keepalived service is responsible for deleting the VIP
            if str(addr.address) in (has_vip, has_vipv6):
                continue
            if has_ipv6 and str(addr.address).startswith('fe80::'):
                continue
            if addr not in addrs_database:
                self.logger.debug('{}: removing {}'.format(name, addr))
                iface.remove_address(addr)
            else:
                if osc.IS_LINUX and not data['int_dhcp']:
                    self.logger.debug('{}: removing possible valid_lft and preferred_lft on {}'.format(name, addr))
                    iface.replace_address(addr)

        if osc.IS_FREEBSD:
            # carp must be configured after removing addresses
            # in case removing the address removes the carp
            if carp_vhid:
                if self.middleware.call_sync('failover.licensed') and not advskew:
                    if 'NO_FAILOVER' in self.middleware.call_sync('failover.disabled_reasons'):
                        if self.middleware.call_sync('failover.vip.get_states')[0]:
                            advskew = 20
                        else:
                            advskew = 80
                    elif self.middleware.call_sync('failover.node') == 'A':
                        advskew = 20
                    else:
                        advskew = 80

                # FIXME: change py-netif to accept str() key
                iface.carp_config = [netif.CarpConfig(carp_vhid, advskew=advskew, key=carp_pass.encode())]
        else:
            if has_vip or has_vipv6:
                if not self.middleware.call_sync('service.started', 'keepalived'):
                    self.middleware.call_sync('service.start', 'keepalived')
                else:
                    self.middleware.call_sync('service.reload', 'keepalived')
                iface.vrrp_config = self.middleware.call_sync('interfaces.vrrp_config', name)

        # Add addresses in database and not configured
        for addr in (addrs_database - addrs_configured):
            # keepalived service is responsible for adding the VIP
            if str(addr.address) in (has_vip, has_vipv6):
                continue
            self.logger.debug('{}: adding {}'.format(name, addr))
            iface.add_address(addr)

        # Apply interface options specified in GUI
        if data['int_options']:
            self.logger.info('{}: applying {}'.format(name, data['int_options']))
            proc = subprocess.Popen(['/sbin/ifconfig', name] + shlex.split(data['int_options']),
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    close_fds=True)
            err = proc.communicate()[1].decode()
            if err:
                self.logger.info('{}: error applying: {}'.format(name, err))

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

        if netif.InterfaceFlags.UP not in iface.flags and 'down' not in data['int_options'].split():
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
        ip = ipaddress.ip_interface('{}/{}'.format(alias['address'], alias['netmask']))
        addr.af = getattr(netif.AddressFamily, 'INET6' if ':' in alias['address'] else 'INET')
        addr.address = ip.ip
        addr.netmask = ip.netmask
        addr.broadcast = ip.network.broadcast_address
        if 'vhid' in alias:
            addr.vhid = alias['vhid']
        return addr
