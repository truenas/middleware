import dns
import enum
import errno
import ipaddress
import socket

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
    async def unregister_dns(self, ad):
        if not ad['allow_dns_updates']:
            return

        netbiosname = (await self.middleware.call('smb.config'))['netbiosname_local']
        domain = ad['domainname']

        hostname = f'{netbiosname}.{domain}'
        try:
            dns_addresses = set([x['address'] for x in await self.middleware.call('dnsclient.forward_lookup', {
                'names': [hostname]
            })])
        except dns.resolver.NXDOMAIN:
            self.logger.warning(
                f'DNS lookup of {hostname}. failed with NXDOMAIN. '
                'This may indicate that DNS entries for the computer account have already been deleted; '
                'however, it may also indicate the presence of larger underlying DNS configuration issues.'
            )
            return

        ips_in_use = set([x['address'] for x in await self.middleware.call('interface.ip_in_use')])
        if not dns_addresses & ips_in_use:
            # raise a CallError here because we don't want someone fat-fingering
            # input and removing an unrelated computer in the domain.
            raise CallError(
                f'DNS records indicate that {hostname} may be associated '
                'with a different computer in the domain. Forward lookup returned the '
                f'following results: {", ".join(dns_addresses)}.'
            )

        payload = []

        for ip in dns_addresses:
            addr = ipaddress.ip_address(ip)
            payload.append({
                'command': 'DELETE',
                'name': hostname,
                'address': str(addr),
                'type': 'A' if addr.version == 4 else 'AAAA'
            })

        try:
            await self.middleware.call('dns.nsupdate', {'ops': payload})
        except CallError as e:
            self.logger.warning(f'Failed to update DNS with payload [{payload}]: {e.errmsg}')

    @private
    async def ipaddresses_to_register(self, data, raise_errors=True):
        validated_ips = []

        if data['clustered']:
            ips = (await self.middleware.call('smb.bindip_choices')).values()
        else:
            ips = [i['address'] for i in (await self.middleware.call('interface.ip_in_use'))]

        if data['bindip']:
            to_check = set(data['bindip']) & set(ips)
        else:
            to_check = set(ips)

        for ip in to_check:
            try:
                result = await self.middleware.call('dnsclient.reverse_lookup', {
                    'addresses': [ip]
                })
            except dns.resolver.NXDOMAIN:
                # This may simply mean entry was not found
                validated_ips.append(ip)

            except dns.resolver.LifetimeTimeout:
                self.logger.warning(
                    '%s: DNS operation timed out while trying to resolve reverse pointer '
                    'for IP address.',
                    ip
                )

            except dns.resolver.NoNameservers:
                self.logger.warning(
                    'No nameservers configured to handle reverse pointer for %s. '
                    'Omitting from list of addresses to use for Active Directory purposes.',
                    ip
                )
                continue

            except Exception:
                # DNS for this IP may be simply wildly misconfigured and time out
                self.logger.warning(
                    'Reverse lookup of %s failed, omitting from list '
                    'of addresses to use for Active Directory purposes.',
                    ip, exc_info=True
                )
                continue

            else:
                if result[0]['target'].casefold() != data['hostname'].casefold() and raise_errors:
                    raise CallError(
                        f'Reverse lookup of {ip} points to {result[0]["target"]}'
                        f'rather than our hostname of {data["hostname"]}.',
                        errno.EINVAL
                    )
                validated_ips.append(ip)

        return validated_ips

    @private
    async def register_dns(self, ad, smb, smb_ha_mode):
        if not ad['allow_dns_updates']:
            return []

        await self.middleware.call('kerberos.check_ticket')
        if smb_ha_mode == 'UNIFIED' and not smb['bindip']:
            bindip = await self.middleware.call('smb.bindip_choices')
        else:
            bindip = smb['bindip']

        hostname = f'{smb["netbiosname_local"]}.{ad["domainname"]}.'
        to_register = await self.ipaddresses_to_register({
            'bindip': bindip,
            'hostname': hostname,
            'clustered': smb_ha_mode == 'CLUSTERED'
        })

        if not to_register:
            raise CallError(
                'No server IP addresses passed DNS validation. '
                'This may indicate an improperly configured reverse zone. '
                'Review middleware log files for details regarding errors encountered.',
                errno.EINVAL
            )

        payload = []

        for ip in to_register:
            addr = ipaddress.ip_address(ip)
            payload.append({
                'command': 'ADD',
                'name': hostname,
                'address': str(addr),
                'type': 'A' if addr.version == 4 else 'AAAA'
            })

        try:
            await self.middleware.call('dns.nsupdate', {'ops': payload})
        except CallError as e:
            self.logger.warning(f'Failed to update DNS with payload [{payload}]: {e.errmsg}')

    @private
    def port_is_listening(self, host, port, timeout=1):
        ret = False

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if timeout:
            s.settimeout(timeout)

        try:
            s.connect((host, port))
            ret = True

        except Exception as e:
            self.logger.debug("connection to %s failed with error: %s",
                              host, e)
            ret = False

        finally:
            s.close()

        return ret

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
                        'on the TrueNAS server.',
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
    def get_n_working_servers(self, domain, srv=SRV.DOMAINCONTROLLER.name, site=None, cnt=1, timeout=10, verbose=False):
        srv_prefix = SRV[srv]
        if site and site != 'Default-First-Site-Name':
            if 'msdcs' in srv_prefix.value:
                parts = srv_prefix.value.split('.')
                srv = '.'.join([parts[0], parts[1]])
                msdcs = '.'.join([parts[2], parts[3]])
                host = f"{srv}.{site}._sites.{msdcs}.{domain}"
            else:
                host = f"{srv_prefix.value}{site}._sites.{domain}."
        else:
            host = f"{srv_prefix.value}{domain}."

        servers = self.middleware.call_sync('dnsclient.forward_lookup', {
            'names': [host],
            'record_types': ['SRV'],
            'query-options': {'order_by': ['priority', 'weight']},
            'dns_client_options': {'lifetime': timeout},
        })

        output = []
        for server in servers:
            if len(output) == cnt:
                break

            if self.port_is_listening(server['target'], server['port'], timeout=timeout):
                output.append({'host': server['target'], 'port': server['port']})

        if verbose:
            self.logger.debug('Request for %d of server type [%s] returned: %s',
                              cnt, srv, output)

        return output

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
