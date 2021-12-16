import contextlib

from middlewared.service import Service, filterable, filterable_returns, private
from middlewared.schema import Dict, IPAddr, ValidationErrors
from middlewared.utils import filter_list


class DNSService(Service):

    class Config:
        cli_namespace = 'network.dns'

    @filterable
    @filterable_returns(Dict('nameserver', IPAddr('nameserver', required=True)))
    def query(self, filters, options):
        """
        Query Name Servers with `query-filters` and `query-options`.
        """
        ips = set()
        with contextlib.suppress(Exception):
            with open('/etc/resolv.conf') as f:
                for line in f:
                    if line.startswith('nameserver'):
                        ip = line[len('nameserver'):].strip()
                        try:
                            IPAddr().validate(ip)  # make sure it's a valid IP (better safe than sorry)
                            ips.add(ip)
                        except ValidationErrors:
                            self.logger.warning('IP %r in resolv.conf does not seem to be valid', ip)
                            continue

        return filter_list([{'nameserver': i} for i in ips], filters, options)

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
        for ns in nameservers:
            resolvconf += 'nameserver {}\n'.format(ns)

        try:
            with open('/etc/resolv.conf', 'w') as f:
                f.write(resolvconf)
        except Exception:
            self.logger.error('Failed to write /etc/resolv.conf', exc_info=True)
