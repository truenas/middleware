from middlewared.service import Service, private

import ipaddress
import netif
import os
import re


class InterfacesService(Service):

    def sync(self):
        """
        Sync interfaces configured in database to the OS.
        """
        interfaces = self.middleware.call('datastore.query', 'network.interfaces')
        for interface in interfaces:
            self.sync_interface(interface['int_interface'])

    @private
    def alias_to_addr(self, alias):
        addr = netif.InterfaceAddress()
        ip = ipaddress.ip_interface(u'{}/{}'.format(alias['address'], alias['netmask']))
        addr.af = getattr(netif.AddressFamily, 'INET6' if ':' in alias['address'] else 'INET')
        addr.address = ip.ip
        addr.netmask = ip.netmask
        addr.broadcast = ip.network.broadcast_address
        return addr

    @private
    def sync_interface(self, name):
        data = self.middleware.call('datastore.query', 'network.interfaces', [('int_interface', '=', name)], {'get': True})
        aliases = self.middleware.call('datastore.query', 'network.alias', [('alias_interface_id', '=', data['id'])])

        iface = netif.get_interface(name)

        addrs_database = set()
        addrs_configured = set([
            a for a in iface.addresses
            if a.af != netif.AddressFamily.LINK
        ])

        if data['int_dhcp']:

            dhclient_pidfile = '/var/run/dhclient.{}.pid'.format(name)
            dhclient_pid = None
            if os.path.exists(dhclient_pidfile):
                with open(dhclient_pidfile, 'r') as f:
                    try:
                        dhclient_pid = int(f.read().strip())
                    except ValueError:
                        pass

            dhclient_running = False
            if dhclient_pid:
                try:
                    os.kill(dhclient_pid, 0)
                except OSError:
                    pass
                else:
                    dhclient_running = True

            if dhclient_running:
                dhclient_leasesfile = '/var/db/dhclient.leases.{}'.format(name)
                if os.path.exists(dhclient_leasesfile):
                    with open(dhclient_leasesfile, 'r') as f:
                        dhclient_leases = f.read()
                    reg_address = re.search(r'fixed-address\s+(.+);', dhclient_leases)
                    reg_netmask = re.search(r'option subnet-mask\s+(.+);', dhclient_leases)
                    if reg_address and reg_netmask:
                        addrs_database.add(self.alias_to_addr({
                            'address': reg_address.group(1),
                            'netmask': reg_netmask.group(1),
                        }))
                    else:
                        self.logger.info('Unable to get address from dhclient')
        else:
            if data['int_ipv4address']:
                addrs_database.add(self.alias_to_addr({
                    'address': data['int_ipv4address'],
                    'netmask': data['int_v4netmaskbit'],
                }))
            if data['int_ipv6address']:
                addrs_database.add(self.alias_to_addr({
                    'address': data['int_ipv6address'],
                    'netmask': data['int_v6netmaskbit'],
                }))

        for alias in aliases:
            if alias['alias_v4address']:
                addrs_database.add(self.alias_to_addr({
                    'address': alias['alias_v4address'],
                    'netmask': alias['alias_v4netmaskbit'],
                }))
            if alias['alias_v6address']:
                addrs_database.add(self.alias_to_addr({
                    'address': alias['alias_v6address'],
                    'netmask': alias['alias_v6netmaskbit'],
                }))

        # Remove addresses configured and not in database
        for addr in (addrs_configured - addrs_database):
            if (
                addr.af == netif.AddressFamily.INET6 and
                str(addr.address).startswith('fe80::')
            ):
                continue
            iface.remove_address(addr)

        # Add addresses in database and not configured
        for addr in (addrs_database - addrs_configured):
            iface.add_address(addr)
