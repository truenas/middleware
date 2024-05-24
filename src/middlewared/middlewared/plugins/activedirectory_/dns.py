import dns
import enum
import errno

from middlewared.service import CallError, private, Service
from middlewared.utils import filter_list


class SRV(enum.Enum):
    DOMAINCONTROLLER = '_ldap._tcp.dc._msdcs.'
    FORESTGLOBALCATALOG = '_ldap._tcp.gc._msdcs.'
    GLOBALCATALOG = '_gc._tcp.'
    KERBEROS = '_kerberos._tcp.'
    KERBEROSDOMAINCONTROLLER = '_kerberos._tcp.dc._msdcs.'
    KPASSWD = '_kpasswd._tcp.'
    LDAP = '_ldap._tcp.'
    PDC = '_ldap._tcp.pdc._msdcs.'


class ActiveDirectoryService(Service):

    class Config:
        service = "activedirectory"

    @private
    async def check_nameservers(self, domain, site=None, lifetime=10):
        def get_host(srv_prefix):
            if site and site != 'Default-First-Site-Name':
                if 'msdcs' in srv_prefix.value:
                    parts = srv_prefix.value.split('.')
                    srv = '.'.join([parts[0], parts[1]])
                    msdcs = '.'.join([parts[2], parts[3]])
                    return f"{srv}.{site}._sites.{msdcs}.{domain}"

                else:
                    return f"{srv_prefix.value}{site}._sites.{domain}."

            return f"{srv_prefix.value}{domain}."

        targets = [get_host(srv_record) for srv_record in [SRV.KERBEROS, SRV.LDAP]]

        for entry in await self.middleware.call('dns.query'):
            servers = []
            for name in targets:
                try:
                    resp = await self.middleware.call('dnsclient.forward_lookup', {
                        'names': [name],
                        'record_types': ['SRV'],
                        'dns_client_options': {
                            'nameservers': [entry['nameserver']],
                            'lifetime': lifetime,
                        }
                    })
                except dns.resolver.NXDOMAIN:
                    raise CallError(
                        f'{name}: Nameserver {entry["nameserver"]} failed to resolve SRV '
                        f'record for domain {domain}. This may indicate a DNS misconfiguration '
                        'on the TrueNAS server. NOTE: When configuring with Active Directory, all '
                        'registered nameservers must be nameservers for the Active Directory domain.',
                        errno.EINVAL
                    )
                except Exception as e:
                    raise CallError(
                        f'{name}: Nameserver {entry["nameserver"]} failed to resolve SRV '
                        f'record for domain {domain} : {e}',
                        errno.EINVAL
                    )

                else:
                    servers.extend(resp)

            for name in targets:
                if not filter_list(servers, [['name', 'C=', name]]):
                    raise CallError(
                        f'Forward lookup of "{name}" failed with nameserver {entry["nameserver"]}. '
                        'This may indicate a DNS misconfiguration on the remote nameserver.',
                        errno.ENOENT
                    )

    @private
    async def netbiosname_is_ours(self, netbios_name, domain_name, lifetime=10):
        try:
            dns_addresses = set([x['address'] for x in await self.middleware.call('dnsclient.forward_lookup', {
                'names': [f'{netbios_name}.{domain_name}'],
                'dns_client_options': {'lifetime': lifetime},
            })])
        except dns.resolver.NXDOMAIN:
            raise CallError(f'DNS forward lookup of [{netbios_name}] failed.', errno.ENOENT)
        except dns.resolver.NoNameservers as e:
            raise CallError(f'DNS forward lookup of netbios name failed: {e}', errno.EFAULT)

        ips_in_use = set((await self.middleware.call('smb.bindip_choices')).keys())

        return bool(dns_addresses & ips_in_use)
