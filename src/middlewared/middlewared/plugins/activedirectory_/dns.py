import enum
import socket
from middlewared.service import private, Service


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
            'name': host, 'record_type': 'SRV', 'query-options': {'order_by': ['priority', 'weight']}
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
