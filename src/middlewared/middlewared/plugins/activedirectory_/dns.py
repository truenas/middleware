import dns
import enum
import errno
import socket

from middlewared.service import CallError, private, Service
from middlewared.plugins.kerberos import krb5ccache
from middlewared.plugins.smb import SMBCmd
from middlewared.utils import run


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
    async def register_dns(self, ad, smb, smb_ha_mode):
        await self.middleware.call('kerberos.check_ticket')
        if not ad['allow_dns_updates'] or smb_ha_mode == 'STANDALONE':
            return

        hostname = f'{smb["netbiosname_local"]}.{ad["domainname"]}.'
        if smb_ha_mode == 'CLUSTERED':
            vips = (await self.middleware.call('smb.bindip_choices')).values()
        else:
            vips = [i['address'] for i in (await self.middleware.call('interface.ip_in_use', {'static': True}))]

        smb_bind_ips = smb['bindip'] if smb['bindip'] else vips
        to_register = set(vips) & set(smb_bind_ips)
        hostname = f'{smb["netbiosname_local"]}.{ad["domainname"]}.'
        cmd = [
            SMBCmd.NET.value,
            '--use-kerberos', 'required',
            '--use-krb5-ccache', krb5ccache.SYSTEM.value,
            'ads', 'dns', 'register', hostname
        ]
        cmd.extend(to_register)
        netdns = await run(cmd, check=False)
        if netdns.returncode != 0:
            self.logger.debug("hostname: %s, ips: %s, text: %s",
                              hostname, to_register, netdns.stderr.decode())

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
    async def check_nameservers(self, domain, site=None):
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

        targets = [get_host(srv_record) for srv_record in [
            SRV.DOMAINCONTROLLER,
            SRV.GLOBALCATALOG,
            SRV.KERBEROS,
            SRV.KERBEROSDOMAINCONTROLLER,
            SRV.KPASSWD,
            SRV.LDAP,
            SRV.PDC
        ]]

        for entry in await self.middleware.call('dns.query'):
            try:
                servers = await self.middleware.call('dnsclient.forward_lookup', {
                    'names': targets,
                    'record_type': 'SRV',
                    'dns_client_options': {'nameservers': [entry['nameserver']]},
                    'query-options': {'order_by': ['priority', 'weight']}
                })
            except dns.resolver.NXDOMAIN:
                raise CallError(
                    f'Nameserver {entry["nameserver"]} failed to resolve SRV records for domain {domain}. '
                    'This may indicate a DNS misconfiguration on the TrueNAS server.',
                    errno.EINVAL
                )

            for name in targets:
                if not any([lambda resp: resp['name'].casefold() == name.casefold(), servers]):
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
            'names': [host], 'record_type': 'SRV', 'query-options': {'order_by': ['priority', 'weight']}
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
