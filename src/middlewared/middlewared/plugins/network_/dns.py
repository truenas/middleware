import contextlib
import ipaddress
import re
import subprocess
import tempfile
from typing import Literal

from pydantic import Field

from middlewared.api import api_method
from middlewared.api.base import BaseModel, single_argument_args, UniqueList, IPv4Nameserver, IPv6Nameserver
from middlewared.api.current import DNSQueryItem
from middlewared.service import Service, filterable_api_method, private
from middlewared.utils import filter_list, MIDDLEWARE_RUN_DIR
from middlewared.plugins.interface.netif import netif
from middlewared.schema import IPAddr, ValidationErrors
from middlewared.service_exception import CallError


class DNSNsUpdateOpA(BaseModel):
    command: Literal['ADD', 'DELETE']
    name: str
    type: Literal['A'] = 'A'
    ttl: int = 3600
    address: IPv4Nameserver
    do_ptr: bool = True


class DNSNsUpdateOpAAAA(DNSNsUpdateOpA):
    type: Literal['AAAA']
    address: IPv6Nameserver


@single_argument_args('data')
class DNSNsUpdateArgs(BaseModel):
    """ Override the nameserver used for nsupdate command. This may be required in
    more complex environments where the nameservers are also KDCs. """
    use_kerberos: bool = True
    ops: UniqueList[DNSNsUpdateOpA | DNSNsUpdateOpAAAA] = Field(min_length=1)
    timeout: int = 30


class DNSNsUpdateResult(BaseModel):
    result: None


class DNSService(Service):

    class Config:
        cli_namespace = 'network.dns'

    @filterable_api_method(item=DNSQueryItem, roles=['NETWORK_INTERFACE_READ'])
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
                ignore = tuple(self.middleware.call_sync('interface.internal_interfaces'))
                interfaces = list()
                for ifname in netif.list_interface_states():
                    if not ifname.startswith(ignore):
                        interfaces.append(ifname)

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

    @api_method(DNSNsUpdateArgs, DNSNsUpdateResult, private=True)
    def nsupdate(self, data):
        if data['use_kerberos']:
            self.middleware.call_sync('kerberos.check_ticket')

        with tempfile.NamedTemporaryFile(dir=MIDDLEWARE_RUN_DIR) as tmpfile:
            ptrs = []
            for entry in data['ops']:
                addr = ipaddress.ip_address(entry['address'])

                directive = ' '.join([
                    'update',
                    entry['command'].lower(),
                    entry['name'],
                    str(entry['ttl']),
                    entry['type'],
                    addr.compressed,
                    '\n'
                ])

                tmpfile.write(directive.encode())
                if entry['do_ptr']:
                    ptrs.append((addr.reverse_pointer, entry['name']))

            if ptrs:
                # additional newline means "send"
                # in this case we send our A and AAAA changes
                # prior to sending our PTR changes
                tmpfile.write(b'\n')

                for ptr in ptrs:
                    reverse_pointer, name = ptr
                    directive = ' '.join([
                        'update',
                        entry['command'].lower(),
                        reverse_pointer,
                        str(entry['ttl']),
                        'PTR',
                        name,
                        '\n'
                    ])
                    tmpfile.write(directive.encode())

            tmpfile.write(b'send\n')
            tmpfile.file.flush()

            cmd = ['nsupdate', '-t', str(data['timeout'])]
            if data['use_kerberos']:
                cmd.append('-g')

            cmd.append(tmpfile.name)
            nsupdate_proc = subprocess.run(cmd, capture_output=True)

            # tsig verify failure is possible if reverse zone is misconfigured
            # Unfortunately, this is quite common and so we have to skip it.
            #
            # Future enhancement can be to perform forward-lookups to validate
            # changes were applied properly
            if nsupdate_proc.returncode and 'tsig verify failure' not in nsupdate_proc.stderr.decode():
                raise CallError(f'nsupdate failed: {nsupdate_proc.stderr.decode()}')
