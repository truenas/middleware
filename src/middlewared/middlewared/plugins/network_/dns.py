import contextlib
import re

from middlewared.service import Service, filterable, filterable_returns, private
from middlewared.schema import Dict, IPAddr, ValidationErrors
from middlewared.utils import filter_list
from middlewared.plugins.interface.netif import netif


class DNSService(Service):

    class Config:
        cli_namespace = 'network.dns'

    @filterable
    @filterable_returns(Dict('nameserver', IPAddr('nameserver', required=True)))
    def query(self, filters, options):
        """
        Query Name Servers with `query-filters` and `query-options`.
        """
        ips = []
        with contextlib.suppress(Exception):
            with open('/etc/resolv.conf') as f:
                for line in filter(lambda x: x.startswith('nameserver'), f):
                    ip = line[len('nameserver'):].strip()
                    try:
                        IPAddr().validate(ip)  # make sure it's a valid IP (better safe than sorry)
                    except ValidationErrors:
                        self.logger.warning('IP %r in resolv.conf does not seem to be valid', ip)
                    else:
                        ip = {'nameserver': ip}
                        if ip not in ips:
                            ips.append(ip)

        return filter_list(ips, filters, options)

    @private
    def sync(self):
        domain = ''
        domains = []
        nameservers = []
        gc = self.middleware.call_sync('datastore.query', 'network.globalconfiguration')[0]
        if gc['gc_domain']:
            domain = gc['gc_domain']
        if gc['gc_domains']:
            domains = gc['gc_domains'].split()
        if gc['gc_nameserver1']:
            nameservers.append(gc['gc_nameserver1'])
        if gc['gc_nameserver2']:
            nameservers.append(gc['gc_nameserver2'])
        if gc['gc_nameserver3']:
            nameservers.append(gc['gc_nameserver3'])

        resolvconf = ''
        if domain:
            resolvconf += 'domain {}\n'.format(domain)
        if domains:
            resolvconf += 'search {}\n'.format(' '.join(domains))

        resolvconf += self.middleware.call_sync('dns.configure_nameservers', nameservers)

        try:
            with open('/etc/resolv.conf', 'w') as f:
                f.write(resolvconf)
        except Exception:
            self.logger.error('Failed to write /etc/resolv.conf', exc_info=True)

    @private
    def configure_nameservers(self, nameservers):
        result = ''
        if nameservers:
            # means nameservers are configured explicitly so add them
            for i in nameservers:
                result += f'nameserver {i}\n'
        else:
            # means there aren't any nameservers configured so let's
            # check to see if dhcp is running on any of the interfaces
            # and if there are, then check dhclient leases file for
            # nameservers that were handed to us via dhcp
            interfaces = self.middleware.call_sync('datastore.query', 'network.interfaces')
            if interfaces:
                interfaces = [i['int_interface'] for i in interfaces if i['int_dhcp']]
            else:
                ignore = self.middleware.call_sync('interface.internal_interfaces')
                ignore.extend(self.middleware.call_sync('failover.internal_interfaces'))
                ignore = tuple(ignore)
                interfaces = list(filter(lambda x: not x.startswith(ignore), netif.list_interfaces().keys()))

            dns_from_dhcp = set()
            for iface in interfaces:
                dhclient_running, dhclient_pid = self.middleware.call_sync('interface.dhclient_status', iface)
                if dhclient_running:
                    leases = self.middleware.call_sync('interface.dhclient_leases', iface)
                    for dns_srvs in re.findall(r'option domain-name-servers (.+)', leases or ''):
                        for dns in dns_srvs.split(';')[0].split(','):
                            dns_from_dhcp.add(f'nameserver {dns.strip()}\n')

            for dns in dns_from_dhcp:
                result += dns

        return result
