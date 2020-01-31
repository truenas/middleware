import datetime
import enum
import errno
import grp
import ipaddress
import json
import ldap
import ldap.sasl
import ntplib
import os
import pwd
import socket
import subprocess
import threading

from dns import resolver
from ldap.controls import SimplePagedResultsControl
from middlewared.plugins.smb import SMBCmd
from middlewared.schema import accepts, Bool, Dict, Int, List, Str
from middlewared.service import job, private, ConfigService, Service, ValidationError, ValidationErrors
from middlewared.service_exception import CallError
import middlewared.sqlalchemy as sa
from middlewared.utils import run, Popen
from middlewared.plugins.directoryservices import DSStatus, SSL
from middlewared.plugins.idmap import DSType
import middlewared.utils.osc as osc
try:
    from samba.dcerpc.messaging import MSG_WINBIND_ONLINE
except ImportError:
    MSG_WINBIND_ONLINE = 9


class neterr(enum.Enum):
    JOINED = 1
    NOTJOINED = 2
    FAULT = 3


class SRV(enum.Enum):
    DOMAINCONTROLLER = '_ldap._tcp.dc._msdcs.'
    FORESTGLOBALCATALOG = '_ldap._tcp.gc._msdcs.'
    GLOBALCATALOG = '_gc._tcp.'
    KERBEROS = '_kerberos._tcp.'
    KERBEROSDOMAINCONTROLLER = '_kerberos._tcp.dc._msdcs.'
    KPASSWD = '_kpasswd._tcp.'
    LDAP = '_ldap._tcp.'
    PDC = '_ldap._tcp.pdc._msdcs.'


class ActiveDirectory_DNS(object):
    def __init__(self, **kwargs):
        super(ActiveDirectory_DNS, self).__init__()
        self.ad = kwargs.get('conf')
        self.logger = kwargs.get('logger')
        return

    def _get_SRV_records(self, host, dns_timeout):
        """
        Set resolver timeout to 1/3 of the lifetime. The timeout defines
        how long to wait before moving on to the next nameserver in resolv.conf
        """
        srv_records = []

        if not host:
            return srv_records

        r = resolver.Resolver()
        r.lifetime = dns_timeout
        r.timeout = r.lifetime / 3

        try:

            answers = r.query(host, 'SRV')
            srv_records = sorted(
                answers,
                key=lambda a: (int(a.priority), int(a.weight))
            )

        except Exception:
            srv_records = []

        return srv_records

    def port_is_listening(self, host, port, timeout=1):
        ret = False

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if timeout:
            s.settimeout(timeout)

        try:
            s.connect((host, port))
            ret = True

        except Exception as e:
            raise CallError(e)

        finally:
            s.close()

        return ret

    def _get_servers(self, srv_prefix):
        """
        We will first try fo find servers based on our AD site. If we don't find
        a server in our site, then we populate list for whole domain. Ticket #27584
        Domain Controllers, Forest Global Catalog Servers, and Kerberos Domain Controllers
        need the site information placed before the 'msdcs' component of the host entry.t
        """
        servers = []
        if not self.ad['domainname']:
            return servers

        if self.ad['site'] and self.ad['site'] != 'Default-First-Site-Name':
            if 'msdcs' in srv_prefix.value:
                parts = srv_prefix.value.split('.')
                srv = '.'.join([parts[0], parts[1]])
                msdcs = '.'.join([parts[2], parts[3]])
                host = f"{srv}.{self.ad['site']}._sites.{msdcs}.{self.ad['domainname']}"
            else:
                host = f"{srv_prefix.value}{self.ad['site']}._sites.{self.ad['domainname']}"
        else:
            host = f"{srv_prefix.value}{self.ad['domainname']}"

        servers = self._get_SRV_records(host, self.ad['dns_timeout'])

        if not servers and self.ad['site']:
            host = f"{srv_prefix.value}{self.ad['domainname']}"
            servers = self._get_SRV_records(host, self.ad['dns_timeout'])

        if SSL(self.ad['ssl']) == SSL.USESSL:
            for server in servers:
                if server.port == 389:
                    server.port = 636

        return servers

    def get_n_working_servers(self, srv=SRV['DOMAINCONTROLLER'], number=1):
        """
        :get_n_working_servers: often only a few working servers are needed and not the whole
        list available on the domain. This takes the SRV record type and number of servers to get
        as arguments.
        """
        servers = self._get_servers(srv)
        found_servers = []
        for server in servers:
            if len(found_servers) == number:
                break

            host = server.target.to_text(True)
            port = int(server.port)
            if self.port_is_listening(host, port, timeout=1):
                server_info = {'host': host, 'port': port}
                found_servers.append(server_info)

        if self.ad['verbose_logging']:
            self.logger.debug(f'Request for [{number}] of server type [{srv.name}] returned: {found_servers}')
        return found_servers


class ActiveDirectory_LDAP(object):
    def __init__(self, **kwargs):
        super(ActiveDirectory_LDAP, self).__init__()
        self.ad = kwargs.get('ad_conf')
        self.hosts = kwargs.get('hosts')
        self.interfaces = kwargs.get('interfaces')
        self.logger = kwargs.get('logger')
        self.pagesize = 1024
        self._isopen = False
        self._handle = None
        self._rootDSE = None
        self._rootDomainNamingContext = None
        self._configurationNamingContext = None
        self._defaultNamingContext = None

    def __enter__(self):
        return self

    def __exit__(self, typ, value, traceback):
        if self._isopen:
            self._close()

    def validate_credentials(self):
        """
        :validate_credentials: simple check to determine whether we can establish
        an ldap session with the credentials that are in the configuration.
        """
        ret = self._open()
        if ret:
            self._close()
        return ret

    def _open(self):
        """
        We can only intialize a single host. In this case,
        we iterate through a list of hosts until we get one that
        works and then use that to set our LDAP handle.
        """
        res = None
        if self._isopen:
            return True

        if self.hosts:
            saved_sasl_bind_error = None
            for server in self.hosts:
                proto = 'ldaps' if SSL(self.ad['ssl']) == SSL.USESSL else 'ldap'
                uri = f"{proto}://{server['host']}:{server['port']}"
                try:
                    self._handle = ldap.initialize(uri)
                except Exception as e:
                    self.logger.debug(
                        f'Failed to initialize ldap connection to [{uri}]: ({e}). Moving to next server.'
                    )
                    continue

                if self.ad['verbose_logging']:
                    self.logger.debug(f'Successfully initialized LDAP server: [{uri}]')

                res = None
                ldap.protocol_version = ldap.VERSION3
                ldap.set_option(ldap.OPT_REFERRALS, 0)
                ldap.set_option(ldap.OPT_NETWORK_TIMEOUT, self.ad['dns_timeout'])

                if SSL(self.ad['ssl']) != SSL.NOSSL:
                    if self.ad['certificate']:
                        ldap.set_option(
                            ldap.OPT_X_TLS_CERTFILE,
                            f"/etc/certificates/{self.ad['certificate']}.crt"
                        )
                        ldap.set_option(
                            ldap.OPT_X_TLS_KEYFILE,
                            f"/etc/certificates/{self.ad['certificate']}.key"
                        )

                    ldap.set_option(
                        ldap.OPT_X_TLS_CACERTFILE,
                        '/etc/ssl/truenas_cacerts.pem'
                    )
                    if self.ad['validate_certificates']:
                        ldap.set_option(
                            ldap.OPT_X_TLS_REQUIRE_CERT,
                            ldap.OPT_X_TLS_DEMAND
                        )
                    else:
                        ldap.set_option(
                            ldap.OPT_X_TLS_REQUIRE_CERT,
                            ldap.OPT_X_TLS_ALLOW
                        )

                    ldap.set_option(ldap.OPT_X_TLS_NEWCTX, 0)

                if SSL(self.ad['ssl']) == SSL.USESTARTTLS:
                    try:
                        self._handle.start_tls_s()

                    except ldap.LDAPError as e:
                        saved_bind_error = e
                        self.logger.debug('Failed to initialize start_tls: %s', e)
                        continue

                if self.ad['certificate'] and SSL(self.ad['ssl']) != SSL.NOSSL:
                    """
                    Active Directory permits two means of establishing an
                    SSL/TLS-protected connection to a DC. The first is by
                    connecting to a DC on a protected LDAPS port (TCP ports 636
                    and 3269 in AD DS, and a configuration-specific port in AD
                    LDS). The second is by connecting to a DC on a regular LDAP
                    port (TCP ports 389 or 3268 in AD DS, and a configuration-
                    specific port in AD LDS), and later sending an
                    LDAP_SERVER_START_TLS_OID extended operation [RFC2830]. In
                    both cases, the DC requests (but does not require) the
                    client's certificate as part of the SSL/TLS handshake
                    [RFC2246]. If the client presents a valid certificate to
                    the DC at that time, it can be used by the DC to
                    authenticate (bind) the connection as the credentials
                    represented by the certificate. See MS-ADTS 5.1.1.2

                    See also RFC2829 7.1: Following the successful completion
                    of TLS negotiation, the client sends an LDAP bind
                    request with the SASL "EXTERNAL" mechanism.
                    """
                    try:
                        res = self._handle.sasl_non_interactive_bind_s('EXTERNAL')
                        if self.ad['verbose_logging']:
                            self.logger.debug(
                                'Successfully bound to [%s] using client certificate.', uri
                            )
                        break

                    except Exception as e:
                        saved_sasl_bind_error = e
                        self.logger.debug('Certificate-based bind failed.', exc_info=True)
                        continue

                try:
                    """
                    While Active Directory permits SASL binds to be performed
                    on an SSL/TLS-protected connection, it does not permit the
                    use of SASL-layer encryption/integrity verification
                    mechanisms on such a connection. While this restriction is
                    present in Active Directory on Windows 2000 Server
                    operating system and later, versions prior to Windows
                    Server 2008 operating system can fail to reject an LDAP
                    bind that is requesting SASL-layer encryption/integrity
                    verification mechanisms when that bind request is sent on a
                    SSL/TLS-protected connection. See MS-ADTS 5.1.1.1.2

                    Samba AD Domain controllers also require the following
                    smb.conf parameter in order to permit SASL_GSSAPI on an SSL/
                    TLS-protected connection:

                    'ldap server require strong auth = allow_sasl_over_tls'
                    """
                    self._handle.set_option(ldap.OPT_X_SASL_NOCANON, 1)
                    if SSL(self.ad['ssl']) != SSL.NOSSL:
                        self._handle.set_option(ldap.OPT_X_SASL_SSF_MAX, 0)

                    self._handle.sasl_gssapi_bind_s()
                    if self.ad['verbose_logging']:
                        self.logger.debug('Successfully bound to [%s] using SASL GSSAPI.', uri)
                    res = True
                    break
                except Exception as e:
                    saved_sasl_bind_error = e
                    self.logger.debug('SASL GSSAPI bind failed.', exc_info=True)

            if res:
                self._isopen = True
            elif saved_bind_error:
                raise CallError(saved_sasl_bind_error)

        return (self._isopen is True)

    def _close(self):
        self._isopen = False
        if self._handle:
            self._handle.unbind()
            self._handle = None

    def _search(self, basedn='', scope=ldap.SCOPE_SUBTREE, filter='', timeout=-1, sizelimit=0):
        if not self._handle:
            self._open()

        result = []
        serverctrls = None
        clientctrls = None
        paged = SimplePagedResultsControl(
            criticality=False,
            size=self.pagesize,
            cookie=''
        )
        paged_ctrls = {SimplePagedResultsControl.controlType: SimplePagedResultsControl}

        page = 0
        while True:
            serverctrls = [paged]

            id = self._handle.search_ext(
                basedn,
                scope,
                filterstr=filter,
                attrlist=None,
                attrsonly=0,
                serverctrls=serverctrls,
                clientctrls=clientctrls,
                timeout=timeout,
                sizelimit=sizelimit
            )

            (rtype, rdata, rmsgid, serverctrls) = self._handle.result3(
                id, resp_ctrl_classes=paged_ctrls
            )

            result.extend(rdata)

            paged.size = 0
            paged.cookie = cookie = None
            for sc in serverctrls:
                if sc.controlType == SimplePagedResultsControl.controlType:
                    cookie = sc.cookie
                    if cookie:
                        paged.cookie = cookie
                        paged.size = self.pagesize

                        break

            if not cookie:
                break

            page += 1

        return result

    def _get_sites(self, distinguishedname):
        sites = []
        basedn = f'CN=Sites,{self._configurationNamingContext}'
        filter = f'(&(objectClass=site)(distinguishedname={distinguishedname}))'
        results = self._search(basedn, ldap.SCOPE_SUBTREE, filter)
        if results:
            for r in results:
                if r[0]:
                    sites.append(r)
        return sites

    def _get_subnets(self):
        subnets = []
        ipv4_subnet_info_lst = []
        ipv6_subnet_info_lst = []
        baseDN = f'CN=Subnets,CN=Sites,{self._configurationNamingContext}'
        results = self._search(baseDN, ldap.SCOPE_SUBTREE, '(objectClass=subnet)')
        if results:
            for r in results:
                if r[0]:
                    subnets.append(r)

        for s in subnets:
            if not s or len(s) < 2:
                continue

            network = site_dn = None
            if 'cn' in s[1]:
                network = s[1]['cn'][0]
                if isinstance(network, bytes):
                    network = network.decode('utf-8')

            else:
                # if the network is None no point calculating
                # anything more so ....
                continue
            if 'siteObject' in s[1]:
                site_dn = s[1]['siteObject'][0]
                if isinstance(site_dn, bytes):
                    site_dn = site_dn.decode('utf-8')

            # Note should/can we do the same skip as done for `network`
            # the site_dn none too?
            st = ipaddress.ip_network(network)

            if st.version == 4:
                ipv4_subnet_info_lst.append({'site_dn': site_dn, 'network': st})
            elif st.version == 6:
                ipv4_subnet_info_lst.append({'site_dn': site_dn, 'network': st})

        if self.ad['verbose_logging']:
            self.logger.debug(f'ipv4_subnet_info: {ipv4_subnet_info_lst}')
            self.logger.debug(f'ipv6_subnet_info: {ipv6_subnet_info_lst}')
        return {'ipv4_subnet_info': ipv4_subnet_info_lst, 'ipv6_subnet_info': ipv6_subnet_info_lst}

    def _initialize_naming_context(self):
        self._rootDSE = self._search('', ldap.SCOPE_BASE, "(objectclass=*)")
        try:
            self._rootDomainNamingContext = self._rootDSE[0][1]['rootDomainNamingContext'][0].decode()
        except Exception as e:
            self.logger.debug(f'Failed to get rootDN: [{e}]')

        try:
            self._defaultNamingContext = self._rootDSE[0][1]['defaultNamingContext'][0].decode()
        except Exception as e:
            self.logger.debug(f'Failed to get baseDN: [{e}]')

        try:
            self._configurationNamingContext = self._rootDSE[0][1]['configurationNamingContext'][0].decode()
        except Exception as e:
            self.logger.debug(f'Failed to get configrationNamingContext: [{e}]')

        if self.ad['verbose_logging']:
            self.logger.debug(f'initialized naming context: rootDN:[{self._rootDomainNamingContext}]')
            self.logger.debug(f'baseDN:[{self._defaultNamingContext}], config:[{self._configurationNamingContext}]')

    def get_netbios_name(self):
        """
        :get_netbios_domain_name: returns the short form of the AD domain name. Confusingly
        titled 'nETBIOSName'. Must not be confused with the netbios hostname of the
        server. For this reason, API calls it 'netbios_domain_name'.
        """
        if not self._handle:
            self._open()
        self._initialize_naming_context()
        filter = f'(&(objectcategory=crossref)(nCName={self._defaultNamingContext}))'
        results = self._search(self._configurationNamingContext, ldap.SCOPE_SUBTREE, filter)
        try:
            netbios_name = results[0][1]['nETBIOSName'][0].decode()

        except Exception as e:
            self._close()
            self.logger.debug(f'Failed to discover short form of domain name: [{e}] res: [{results}]')
            netbios_name = None

        self._close()
        if self.ad['verbose_logging']:
            self.logger.debug(f'Query for nETBIOSName from LDAP returned: [{netbios_name}]')
        return netbios_name

    def locate_site(self):
        """
        Returns the AD site that the NAS is a member of. AD sites are used
        to break up large domains into managable chunks typically based on physical location.
        Although samba handles AD sites independent of the middleware. We need this
        information to determine which kerberos servers to use in the krb5.conf file to
        avoid communicating with a KDC on the other side of the world.
        In Windows environment, this is discovered via CLDAP query for closest DC. We
        can't do this, and so we have to rely on comparing our network configuration with
        site and subnet information obtained through LDAP queries.
        """
        if not self._handle:
            self._open()
        ipv4_site = None
        ipv6_site = None
        self._initialize_naming_context()
        subnets = self._get_subnets()
        for nic in self.interfaces:
            for alias in nic['aliases']:
                if alias['type'] == 'INET':
                    if ipv4_site is not None:
                        continue
                    ipv4_addr_obj = ipaddress.ip_address(alias['address'])
                    for subnet in subnets['ipv4_subnet_info']:
                        if ipv4_addr_obj in subnet['network']:
                            sinfo = self._get_sites(distinguishedname=subnet['site_dn'])[0]
                            if sinfo and len(sinfo) > 1:
                                ipv4_site = sinfo[1]['cn'][0].decode()
                                break

                if alias['type'] == 'INET6':
                    if ipv6_site is not None:
                        continue
                    ipv6_addr_obj = ipaddress.ip_address(alias['address'])
                    for subnet in subnets['ipv6_subnet_info']:
                        if ipv6_addr_obj in subnet['network']:
                            sinfo = self._get_sites(distinguishedname=subnet['site_dn'])[0]
                            if sinfo and len(sinfo) > 1:
                                ipv6_site = sinfo[1]['cn'][0].decode()
                                break

        if ipv4_site and ipv6_site and ipv4_site == ipv6_site:
            return ipv4_site

        if ipv4_site:
            return ipv4_site

        if not ipv4_site and ipv6_site:
            return ipv6_site

        return None


class ActiveDirectoryModel(sa.Model):
    __tablename__ = 'directoryservice_activedirectory'

    id = sa.Column(sa.Integer(), primary_key=True)
    ad_domainname = sa.Column(sa.String(120))
    ad_bindname = sa.Column(sa.String(120))
    ad_bindpw = sa.Column(sa.String(120))
    ad_ssl = sa.Column(sa.String(120))
    ad_validate_certificates = sa.Column(sa.Boolean())
    ad_verbose_logging = sa.Column(sa.Boolean())
    ad_allow_trusted_doms = sa.Column(sa.Boolean())
    ad_use_default_domain = sa.Column(sa.Boolean())
    ad_allow_dns_updates = sa.Column(sa.Boolean())
    ad_disable_freenas_cache = sa.Column(sa.Boolean())
    ad_site = sa.Column(sa.String(120), nullable=True)
    ad_timeout = sa.Column(sa.Integer())
    ad_dns_timeout = sa.Column(sa.Integer())
    ad_nss_info = sa.Column(sa.String(120), nullable=True)
    ad_ldap_sasl_wrapping = sa.Column(sa.String(120))
    ad_enable = sa.Column(sa.Boolean())
    ad_certificate_id = sa.Column(sa.ForeignKey('system_certificate.id'), index=True, nullable=True)
    ad_kerberos_realm_id = sa.Column(sa.ForeignKey('directoryservice_kerberosrealm.id', ondelete='SET NULL'),
                                     index=True, nullable=True)
    ad_kerberos_principal = sa.Column(sa.String(255))
    ad_createcomputer = sa.Column(sa.String(255))


class ActiveDirectoryService(ConfigService):
    class Config:
        service = "activedirectory"
        datastore = 'directoryservice.activedirectory'
        datastore_extend = "activedirectory.ad_extend"
        datastore_prefix = "ad_"

    @private
    async def ad_extend(self, ad):
        smb = await self.middleware.call('smb.config')
        smb_ha_mode = await self.middleware.call('smb.get_smb_ha_mode')
        if smb_ha_mode == 'STANDALONE':
            ad.update({
                'netbiosname': smb['netbiosname'],
                'netbiosalias': smb['netbiosalias']
            })
        elif smb_ha_mode == 'UNIFIED':
            ngc = await self.middleware.call('network.configuration.config')
            ad.update({
                'netbiosname': ngc['hostname_virtual'],
                'netbiosalias': smb['netbiosalias']
            })
        elif smb_ha_mode == 'LEGACY':
            ngc = await self.middleware.call('network.configuration.config')
            ad.update({
                'netbiosname': ngc['hostname'],
                'netbiosname_b': ngc['hostname_b'],
                'netbiosalias': smb['netbiosalias']
            })

        for key in ['ssl', 'nss_info', 'ldap_sasl_wrapping']:
            if key in ad and ad[key] is not None:
                ad[key] = ad[key].upper()

        for key in ['kerberos_realm', 'certificate']:
            if ad[key] is not None:
                ad[key] = ad[key]['id']

        return ad

    @private
    async def ad_compress(self, ad):
        """
        Convert kerberos realm to id. Force domain to upper-case. Remove
        foreign entries.
        kinit will fail if domain name is lower-case.
        """
        for key in ['netbiosname', 'netbiosalias', 'netbiosname_a', 'netbiosname_b']:
            if key in ad:
                ad.pop(key)

        for key in ['ssl', 'nss_info', 'ldap_sasl_wrapping']:
            if ad[key] is not None:
                ad[key] = ad[key].lower()

        return ad

    @accepts()
    async def nss_info_choices(self):
        """
        Returns list of available LDAP schema choices.
        """
        return await self.middleware.call('directoryservices.nss_info_choices', 'ACTIVEDIRECTORY')

    @accepts()
    async def ssl_choices(self):
        """
        Returns list of SSL choices.
        """
        return await self.middleware.call('directoryservices.ssl_choices', 'ACTIVEDIRECTORY')

    @accepts()
    async def sasl_wrapping_choices(self):
        """
        Returns list of sasl wrapping choices.
        """
        return await self.middleware.call('directoryservices.sasl_wrapping_choices', 'ACTIVEDIRECTORY')

    @private
    async def update_netbios_data(self, old, new):
        smb_ha_mode = await self.middleware.call('smb.get_smb_ha_mode')
        must_update = False
        for key in ['netbiosname', 'netbiosalias', 'netbiosname_a', 'netbiosname_b']:
            if key in new and old[key] != new[key]:
                must_update = True if new[key] else False

        if smb_ha_mode == 'STANDALONE' and must_update:
            await self.middleware.call(
                'smb.update',
                {
                    'netbiosname': new['netbiosname'],
                    'netbiosalias': new['netbiosalias']
                }
            )

        elif smb_ha_mode == 'UNIFIED' and must_update:
            await self.middleware.call('smb.update', {'netbiosalias': new['netbiosalias']})
            await self.middleware.call('network.configuration.update', {'hostname_virtual': new['netbiosname']})

        elif smb_ha_mode == 'LEGACY' and must_update:
            await self.middleware.call('smb.update', {'netbiosalias': new['netbiosalias']})
            await self.middleware.call(
                'network.configuration.update',
                {
                    'hostname': new['netbiosname'],
                    'hostname_b': new['netbiosname_b']
                }
            )
        return

    @private
    async def common_validate(self, new, old, verrors):
        if not new["enable"]:
            return

        if not new["bindpw"] and not new["kerberos_principal"]:
            verrors.add(
                "activedirectory_update.bindname",
                "Bind credentials or kerberos keytab are required to join an AD domain."
            )
        if new["bindpw"] and new["kerberos_principal"]:
            verrors.add(
                "activedirectory_update.kerberos_principal",
                "Simultaneous keytab and password authentication are not permitted."
            )
        if not new["domainname"]:
            verrors.add(
                "activedirectory_update.domainname",
                "AD domain name is required."
            )

    @accepts(Dict(
        'activedirectory_update',
        Str('domainname', required=True),
        Str('bindname'),
        Str('bindpw', private=True),
        Str('ssl', default='OFF', enum=['OFF', 'ON', 'START_TLS']),
        Int('certificate', null=True),
        Bool('validate_certificates', default=True),
        Bool('verbose_logging'),
        Bool('use_default_domain'),
        Bool('allow_trusted_doms'),
        Bool('allow_dns_updates'),
        Bool('disable_freenas_cache'),
        Str('site', null=True),
        Int('kerberos_realm', null=True),
        Str('kerberos_principal', null=True),
        Int('timeout', default=60),
        Int('dns_timeout', default=10),
        Str('nss_info', null=True, default='', enum=['SFU', 'SFU20', 'RFC2307']),
        Str('ldap_sasl_wrapping', default='SIGN', enum=['PLAIN', 'SIGN', 'SEAL']),
        Str('createcomputer'),
        Str('netbiosname'),
        Str('netbiosname_b'),
        List('netbiosalias'),
        Bool('enable'),
        update=True
    ))
    async def do_update(self, data):
        """
        Update active directory configuration.
        `domainname` full DNS domain name of the Active Directory domain.

        `bindname` username used to perform the intial domain join.

        `bindpw` password used to perform the initial domain join. User-
        provided credentials are used to obtain a kerberos ticket, which
        is used to perform the actual domain join.

        `ssl` establish SSL/TLS-protected connections to the DCs in the
        Active Directory domain.

        `certificate` LDAPs client certificate to be used for certificate-
        based authentication in the AD domain. If certificate-based
        authentication is not configured, SASL GSSAPI binds will be performed.

        `validate_certificates` specifies whether to perform checks on server
        certificates in a TLS session. If enabled, TLS_REQCERT demand is set.
        The server certificate is requested. If no certificate is provided or
        if a bad certificate is provided, the session is immediately terminated.
        If disabled, TLS_REQCERT allow is set. The server certificate is
        requested, but all errors are ignored.

        `verbose_logging` increase logging during the domain join process.

        `use_default_domain` controls whether domain users and groups have
        the pre-windows 2000 domain name prepended to the user account. When
        enabled, the user appears as "administrator" rather than
        "EXAMPLE\administrator"

        `allow_trusted_doms` enable support for trusted domains. If this
        parameter is enabled, then separate idmap backends _must_ be configured
        for each trusted domain, and the idmap cache should be cleared.

        `allow_dns_updates` during the domain join process, automatically
        generate DNS entries in the AD domain for the NAS. If this is disabled,
        then a domain administrator must manually add appropriate DNS entries
        for the NAS. This parameter is recommended for TrueNAS HA servers.

        `disable_freenas_cache` disables active caching of AD users and groups.
        When disabled, only users cached in winbind's internal cache are
        visible in GUI dropdowns. Disabling active caching is recommended
        in environments with a large amount of users.

        `site` AD site of which the NAS is a member. This parameter is auto-
        detected during the domain join process. If no AD site is configured
        for the subnet in which the NAS is configured, then this parameter
        appears as 'Default-First-Site-Name'. Auto-detection is only performed
        during the initial domain join.

        `kerberos_realm` in which the server is located. This parameter is
        automatically populated during the initial domain join. If the NAS has
        an AD site configured and that site has multiple kerberos servers, then
        the kerberos realm is automatically updated with a site-specific
        configuration to use those servers. Auto-detection is only performed
        during initial domain join.

        `kerberos_principal` kerberos principal to use for AD-related
        operations outside of Samba. After intial domain join, this field is
        updated with the kerberos principal associated with the AD machine
        account for the NAS.

        `nss_info` controls how Winbind retrieves Name Service Information to
        construct a user's home directory and login shell. This parameter
        is only effective if the Active Directory Domain Controller supports
        the Microsoft Services for Unix (SFU) LDAP schema.

        `timeout` timeout value for winbind-related operations. This value may
        need to be increased in  environments with high latencies for
        communications with domain controllers or a large number of domain
        controllers. Lowering the value may cause status checks to fail.

        `dns_timeout` timeout value for DNS queries during the initial domain
        join. This value is also set as the NETWORK_TIMEOUT in the ldap config
        file.

        `ldap_sasl_wrapping` defines whether ldap traffic will be signed or
        signed and encrypted (sealed). LDAP traffic that does not originate
        from Samba defaults to using GSSAPI signing unless it is tunnelled
        over LDAPs.

        `createcomputer` Active Directory Organizational Unit in which new
        computer accounts are created.

        The OU string is read from top to bottom without RDNs. Slashes ("/")
        are used as delimiters, like `Computers/Servers/NAS`. The backslash
        ("\\") is used to escape characters but not as a separator. Backslashes
        are interpreted at multiple levels and might require doubling or even
        quadrupling to take effect.

        When this field is blank, new computer accounts are created in the
        Active Directory default OU.

        The Active Directory service is started after a configuration
        update if the service was initially disabled, and the updated
        configuration sets `enable` to `True`. The Active Directory
        service is stopped if `enable` is changed to `False`. If the
        configuration is updated, but the initial `enable` state is `True`, and
        remains unchanged, then the samba server is only restarted.

        During the domain join, a kerberos keytab for the newly-created AD
        machine account is generated. It is used for all future
        LDAP / AD interaction and the user-provided credentials are removed.
        """
        verrors = ValidationErrors()
        old = await self.config()
        new = old.copy()
        new.update(data)
        new['domainname'] = new['domainname'].upper()
        try:
            await self.update_netbios_data(old, new)
        except Exception as e:
            raise ValidationError('activedirectory_update.netbiosname', str(e))

        await self.common_validate(new, old, verrors)

        if verrors:
            raise verrors

        if new['enable'] and not old['enable']:
            try:
                await self.middleware.run_in_thread(self.validate_credentials, new)
            except Exception as e:
                raise ValidationError(
                    "activedirectory_update.bindpw",
                    f"Failed to validate bind credentials: {e}"
                )

            try:
                await self.middleware.run_in_thread(self.validate_domain, new)
            except Exception as e:
                raise ValidationError(
                    "activedirectory_update",
                    f"Failed to validate domain configuration: {e}"
                )

        new = await self.ad_compress(new)
        await self.middleware.call(
            'datastore.update',
            'directoryservice.activedirectory',
            old['id'],
            new,
            {'prefix': 'ad_'}
        )

        start = False
        stop = False

        if not old['enable']:
            if new['enable']:
                start = True
        else:
            if not new['enable']:
                stop = True

        if stop:
            await self.stop()
        if start:
            await self.start()

        if not stop and not start and new['enable']:
            await self.middleware.call('service.restart', 'cifs')

        return await self.config()

    @private
    async def set_state(self, state):
        return await self.middleware.call('directoryservices.set_state', {'activedirectory': state.name})

    @accepts()
    async def get_state(self):
        """
        Wrapper function for 'directoryservices.get_state'. Returns only the state of the
        Active Directory service.
        """
        return (await self.middleware.call('directoryservices.get_state'))['activedirectory']

    @private
    async def set_idmap(self, trusted_domains, our_domain):
        idmap = await self.middleware.call('idmap.query',
                                           [('id', '=', DSType.DS_TYPE_ACTIVEDIRECTORY.value)],
                                           {'get': True})
        idmap_id = idmap.pop('id')
        if not idmap['range_low']:
            idmap['range_low'], idmap['range_high'] = await self.middleware.call('idmap.get_next_idmap_range')
        idmap['dns_domain_name'] = our_domain.upper()
        await self.middleware.call('idmap.update', idmap_id, idmap)
        if trusted_domains:
            await self.middleware.call('idmap.autodiscover_trusted_domains')

    @private
    async def start(self):
        """
        Start AD service. In 'UNIFIED' HA configuration, only start AD service
        on active storage controller.
        """
        ad = await self.config()
        smb = await self.middleware.call('smb.config')
        smb_ha_mode = await self.middleware.call('smb.get_smb_ha_mode')
        if smb_ha_mode == 'UNIFIED':
            if await self.middleware.call('failover.status') != 'MASTER':
                return

        state = await self.get_state()
        if state in [DSStatus['JOINING'], DSStatus['LEAVING']]:
            raise CallError(f'Active Directory Service has status of [{state}]. Wait until operation completes.', errno.EBUSY)

        await self.set_state(DSStatus['JOINING'])
        if ad['verbose_logging']:
            self.logger.debug('Starting Active Directory service for [%s]', ad['domainname'])
        await self.middleware.call('datastore.update', self._config.datastore, ad['id'], {'ad_enable': True})
        await self.middleware.call('etc.generate', 'hostname')

        """
        Kerberos realm field must be populated so that we can perform a kinit
        and use the kerberos ticket to execute 'net ads' commands.
        """
        if not ad['kerberos_realm']:
            realms = await self.middleware.call('kerberos.realm.query', [('realm', '=', ad['domainname'])])

            if realms:
                await self.middleware.call('datastore.update', self._config.datastore, ad['id'], {'ad_kerberos_realm': realms[0]['id']})
            else:
                await self.middleware.call('datastore.insert', 'directoryservice.kerberosrealm', {'krb_realm': ad['domainname'].upper()})
            ad = await self.config()

        await self.middleware.call('kerberos.start')

        """
        'workgroup' is the 'pre-Windows 2000 domain name'. It must be set to the nETBIOSName value in Active Directory.
        This must be properly configured in order for Samba to work correctly as an AD member server.
        'site' is the ad site of which the NAS is a member. If sites and subnets are unconfigured this will
        default to 'Default-First-Site-Name'.
        """

        if not ad['site']:
            new_site = await self.middleware.run_in_thread(self.get_site)
            if new_site != 'Default-First-Site-Name':
                ad = await self.config()
                site_indexed_kerberos_servers = await self.middleware.run_in_thread(self.get_kerberos_servers)

                if site_indexed_kerberos_servers:
                    await self.middleware.call(
                        'datastore.update',
                        'directoryservice.kerberosrealm',
                        ad['kerberos_realm']['id'],
                        site_indexed_kerberos_servers
                    )
                    await self.middleware.call('etc.generate', 'kerberos')

        if not smb['workgroup'] or smb['workgroup'] == 'WORKGROUP':
            await self.middleware.run_in_thread(self.get_netbios_domain_name)

        await self.middleware.call('etc.generate', 'smb')

        """
        Check response of 'net ads testjoin' to determine whether the server needs to be joined to Active Directory.
        Only perform the domain join if we receive the exact error code indicating that the server is not joined to
        Active Directory. 'testjoin' will fail if the NAS boots before the domain controllers in the environment.
        In this case, samba should be started, but the directory service reported in a FAULTED state.
        """

        ret = await self._net_ads_testjoin(smb['workgroup'])
        if ret == neterr.NOTJOINED:
            self.logger.debug(f"Test join to {ad['domainname']} failed. Performing domain join.")
            await self._net_ads_join()
            await self._register_virthostname(ad, smb, smb_ha_mode)
            if smb_ha_mode != 'LEGACY':
                """
                Manipulating the SPN entries must be done with elevated privileges. Add NFS service
                principals while we have these on-hand. Once added, force a refresh of the system
                keytab so that the NFS principal will be available for gssd.
                """
                must_update_trust_pw = await self._net_ads_setspn([
                    f'nfs/{ad["netbiosname"].upper()}.{ad["domainname"]}',
                    f'nfs/{ad["netbiosname"].upper()}'
                ])
                if must_update_trust_pw:
                    try:
                        await self.change_trust_account_pw()
                    except Exception as e:
                        self.logger.debug(
                            "Failed to change trust password after setting NFS SPN: [%s]."
                            "This may impact kerberized NFS sessions until the next scheduled trust account password change", e
                        )

                kt_id = await self.middleware.call('kerberos.keytab.store_samba_keytab')
                if kt_id:
                    self.logger.debug('Successfully generated keytab for computer account. Clearing bind credentials')
                    await self.middleware.call(
                        'datastore.update',
                        'directoryservice.activedirectory',
                        ad['id'],
                        {'ad_bindpw': '', 'ad_kerberos_principal': f'{ad["netbiosname"].upper()}$@{ad["domainname"]}'}
                    )
                    ad = await self.config()

            ret = neterr.JOINED
            await self.middleware.call('service.update', 'cifs', {'enable': True})
            await self.set_idmap(ad['allow_trusted_doms'], ad['domainname'])
            await self.middleware.call('activedirectory.set_ntp_servers')

        await self.middleware.call('service.restart', 'cifs')
        await self.middleware.call('etc.generate', 'pam')
        await self.middleware.call('etc.generate', 'nss')
        if ret == neterr.JOINED:
            await self.set_state(DSStatus['HEALTHY'])
            await self.middleware.call('admonitor.start')
            await self.middleware.call('activedirectory.get_cache')
            if ad['verbose_logging']:
                self.logger.debug('Successfully started AD service for [%s].', ad['domainname'])
        else:
            await self.set_state(DSStatus['FAULTED'])
            self.logger.debug('Server is joined to domain [%s], but is in a faulted state.', ad['domainname'])

    @private
    async def stop(self):
        ad = await self.config()
        await self.middleware.call('datastore.update', self._config.datastore, ad['id'], {'ad_enable': False})
        await self.set_state(DSStatus['LEAVING'])
        await self.middleware.call('admonitor.stop')
        await self.middleware.call('etc.generate', 'hostname')
        await self.middleware.call('kerberos.stop')
        await self.middleware.call('etc.generate', 'smb')
        await self.middleware.call('service.restart', 'cifs')
        await self.middleware.call('etc.generate', 'pam')
        await self.middleware.call('etc.generate', 'nss')
        await self.set_state(DSStatus['DISABLED'])

    @private
    def validate_credentials(self, ad=None):
        """
        Performs test bind to LDAP server in AD environment. Since we are performing
        sasl_gssapi binds, we must first configure kerberos and obtain a ticket.
        """
        ret = False
        if ad is None:
            ad = self.middleware.call_sync('activedirectory.config')

        if ad['kerberos_principal']:
            self.middleware.call_sync('etc.generate', 'kerberos')
            kinit = subprocess.run(['kinit', '--renewable', '-k', ad['kerberos_principal']], capture_output=True)
            if kinit.returncode != 0:
                raise CallError(
                    f'kinit with principal {ad["kerberos_principal"]} failed with error {kinit.stderr.decode()}'
                )
        else:
            if not self.middleware.call_sync('kerberos.realm.query', [('realm', '=', ad['domainname'])]):
                self.middleware.call_sync(
                    'datastore.insert',
                    'directoryservice.kerberosrealm',
                    {'krb_realm': ad['domainname'].upper()}
                )
            self.middleware.call_sync('etc.generate', 'kerberos')
            kinit = subprocess.run([
                '/usr/bin/kinit',
                '--renewable',
                '--password-file=STDIN',
                f'{ad["bindname"]}@{ad["domainname"]}'],
                input=ad['bindpw'].encode(),
                capture_output=True
            )
            if kinit.returncode != 0:
                realm = self.middleware.call_sync(
                    'kerberos.realm.query',
                    [('realm', '=', ad['domainname'])],
                    {'get': True}
                )
                self.middleware.call_sync('kerberos.realm.delete', realm['id'])
                raise CallError(
                    f"kinit for domain [{ad['domainname']}] with password failed: {kinit.stderr.decode()}"
                )

        dcs = ActiveDirectory_DNS(conf=ad, logger=self.logger).get_n_working_servers(SRV['DOMAINCONTROLLER'], 3)
        if not dcs:
            raise CallError('Failed to open LDAP socket to any DC in domain.')

        tmpconf = ad.copy()
        if tmpconf['certificate']:
            tmpconf['certificate'] = self.middleware.call_sync(
                'certificate.query',
                [('id', '=', ad['certificate'])],
                {'get': True}
            )['name']

        with ActiveDirectory_LDAP(ad_conf=tmpconf, logger=self.logger, hosts=dcs) as AD_LDAP:
            ret = AD_LDAP.validate_credentials()

        return ret

    @private
    def check_clockskew(self, ad=None):
        """
        Uses DNS srv records to determine server with PDC emulator FSMO role and
        perform NTP query to determine current clockskew. Raises exception if
        clockskew exceeds 3 minutes, otherwise returns dict with hostname of
        PDC emulator, time as reported from PDC emulator, and time difference
        between the PDC emulator and the NAS.
        """
        permitted_clockskew = datetime.timedelta(minutes=3)
        nas_time = datetime.datetime.now()
        if not ad:
            ad = self.middleware.call_sync('activedirectory.config')

        pdc = ActiveDirectory_DNS(conf=ad, logger=self.logger).get_n_working_servers(SRV['PDC'], 1)
        c = ntplib.NTPClient()
        response = c.request(pdc[0]['host'])
        ntp_time = datetime.datetime.fromtimestamp(response.tx_time)
        clockskew = abs(ntp_time - nas_time)
        if clockskew > permitted_clockskew:
            raise CallError(f'Clockskew between {pdc[0]["host"]} and NAS exceeds 3 minutes')
        return {'pdc': str(pdc[0]['host']), 'timestamp': str(ntp_time), 'clockskew': str(clockskew)}

    @private
    def validate_domain(self, data=None):
        """
        Methods used to determine AD domain health.
        """
        self.middleware.call_sync('activedirectory.check_clockskew', data)

    @private
    async def _get_cached_srv_records(self, srv=SRV['DOMAINCONTROLLER']):
        """
        Avoid unecessary DNS lookups. These can potentially be expensive if DNS
        is flaky. Try site-specific results first, then try domain-wide ones.
        """
        servers = []
        if await self.middleware.call('cache.has_key', f'SRVCACHE_{srv.name}_SITE'):
            servers = await self.middleware.call('cache.get', f'SRVCACHE_{srv.name}_SITE')

        if not servers and await self.middleware.call('cache.has_key', f'SRVCACHE_{srv.name}'):
            servers = await self.middleware.call('cache.get', f'SRVCACHE_{srv.name}')

        return servers

    @private
    async def _set_cached_srv_records(self, srv=None, site=None, results=None):
        """
        Cache srv record lookups for 24 hours
        """
        if not srv:
            raise CallError('srv record type not specified', errno.EINVAL)

        if site:
            await self.middleware.call('cache.put', f'SRVCACHE_{srv.name}_SITE', results, 86400)
        else:
            await self.middleware.call('cache.put', f'SRVCACHE_{srv.name}', results, 86400)
        return True

    @accepts()
    async def started(self):
        """
        Issue a no-effect command to our DC. This checks if our secure channel connection to our
        domain controller is still alive. It has much less impact than wbinfo -t.
        Default winbind request timeout is 60 seconds, and can be adjusted by the smb4.conf parameter
        'winbind request timeout ='
        """
        verrors = ValidationErrors()
        config = await self.config()
        if not config['enable']:
            return False

        await self.common_validate(config, config, verrors)

        try:
            verrors.check()
        except Exception:
            await self.middleware.call(
                'datastore.update',
                'directoryservice.activedirectory',
                config['id'],
                {'ad_enable': False}
            )
            raise CallError('Automatically disabling ActiveDirectory service due to invalid configuration.',
                            errno.EINVAL)

        netlogon_ping = await run([SMBCmd.WBINFO.value, '-P'], check=False)
        if netlogon_ping.returncode != 0:
            raise CallError(netlogon_ping.stderr.decode().strip('\n'))

        return True

    @private
    async def _register_virthostname(self, ad, smb, smb_ha_mode):
        """
        This co-routine performs virtual hostname aware
        dynamic DNS updates after joining AD to register
        CARP addresses.
        """
        if not ad['allow_dns_updates'] or smb_ha_mode == 'STANDALONE':
            return

        vhost = (await self.middleware.call('network.configuration.config'))['hostname_virtual']
        carp_ips = set(await self.middleware.call('failover.get_ips'))
        smb_bind_ips = set(smb['bindip']) if smb['bindip'] else carp_ips
        to_register = carp_ips & smb_bind_ips
        hostname = f'{vhost}.{ad["domainname"]}'
        cmd = [SMBCmd.NET.value, '-k', 'ads', 'dns', 'register', hostname]
        cmd.extend(to_register)
        netdns = await run(cmd, check=False)
        if netdns.returncode != 0:
            self.logger.debug("hostname: %s, ips: %s, text: %s",
                              hostname, to_register, netdns.stderr.decode())

    @private
    async def _net_ads_join(self):
        ad = await self.config()
        if ad['createcomputer']:
            netads = await run([
                SMBCmd.NET.value, '-k', '-U', ad['bindname'], '-d', '5',
                'ads', 'join', f'createcomputer={ad["createcomputer"]}',
                ad['domainname']], check=False)
        else:
            netads = await run([
                SMBCmd.NET.value, '-k', '-U', ad['bindname'], '-d', '5',
                'ads', 'join', ad['domainname']], check=False)

        if netads.returncode != 0:
            await self.set_state(DSStatus['FAULTED'])
            raise CallError(f'Failed to join [{ad["domainname"]}]: [{netads.stdout.decode().strip()}]')

    @private
    async def _net_ads_testjoin(self, workgroup):
        ad = await self.config()
        netads = await run([
            SMBCmd.NET.value, '-k', '-w', workgroup,
            '-d', '5', 'ads', 'testjoin', ad['domainname']],
            check=False
        )
        if netads.returncode != 0:
            errout = netads.stderr.decode().strip()
            self.logger.debug(f'net ads testjoin failed with error: [{errout}]')
            if '0xfffffff6' in errout:
                return neterr.NOTJOINED
            else:
                return neterr.FAULT

        return neterr.JOINED

    @private
    async def _net_ads_setspn(self, spn_list):
        for spn in spn_list:
            netads = await run([
                SMBCmd.NET.value, '-k', 'ads', 'setspn',
                'add', spn
            ], check=False)
            if netads.returncode != 0:
                self.logger.debug('Failed to set spn entry [%s]: %s',
                                  spn, netads.stderr.decode().strip())
                return False

        return True

    @accepts()
    async def get_spn_list(self):
        """
        Return list of kerberos SPN entries registered for the server's Active
        Directory computer account. This may not reflect the state of the
        server's current kerberos keytab.
        """
        spnlist = []
        netads = await run([SMBCmd.NET.value, '-k', 'ads', 'setspn', 'list'], check=False)
        if netads.returncode != 0:
            raise CallError(
                f"Failed to generate SPN list: [{netads.stderr.decode().strip()}]"
            )

        for spn in netads.stdout.decode().splitlines():
            if len(spn.split('/')) != 2:
                continue
            spnlist.append(spn.strip())

        return spnlist

    @accepts()
    async def change_trust_account_pw(self):
        """
        Force an update of the AD machine account password. This can be used to
        refresh the Kerberos principals in the server's system keytab.
        """
        workgroup = (await self.middleware.call('smb.config'))['workgroup']
        netads = await run([SMBCmd.NET.value, '-k', 'ads', '-w', workgroup, 'changetrustpw'], check=False)
        if netads.returncode != 0:
            raise CallError(
                f"Failed to update trust password: [{netads.stderr.decode().strip()}]"
            )

    @accepts()
    async def domain_info(self):
        """
        Returns the following information about the currently joined domain:

        `LDAP server` IP address of current LDAP server to which TrueNAS is connected.

        `LDAP server name` DNS name of LDAP server to which TrueNAS is connected

        `Realm` Kerberos realm

        `LDAP port`

        `Server time` timestamp.

        `KDC server` Kerberos KDC to which TrueNAS is connected

        `Server time offset` current time offset from DC.

        `Last machine account password change`. timestamp
        """
        netads = await run([SMBCmd.NET.value, '-k', 'ads', 'info', '--json'], check=False)
        if netads.returncode != 0:
            raise CallError(netads.stderr.decode())

        return json.loads(netads.stdout.decode())

    @private
    def get_netbios_domain_name(self):
        """
        The 'workgroup' parameter must be set correctly in order for AD join to
        succeed. This is based on the short form of the domain name, which was defined
        by the AD administrator who deployed originally deployed the AD enviornment.
        The only way to reliably get this is to query the LDAP server. This method
        queries and sets it.
        """

        ret = False
        ad = self.middleware.call_sync('activedirectory.config')
        smb = self.middleware.call_sync('smb.config')
        dcs = self.middleware.call_sync('activedirectory._get_cached_srv_records', SRV['DOMAINCONTROLLER'])
        set_new_cache = True if not dcs else False

        if not dcs:
            dcs = ActiveDirectory_DNS(conf=ad, logger=self.logger).get_n_working_servers(SRV['DOMAINCONTROLLER'], 3)

        if set_new_cache:
            self.middleware.call_sync('activedirectory._set_cached_srv_records', SRV['DOMAINCONTROLLER'], ad['site'], dcs)

        if ad['certificate']:
            ad['certificate'] = self.middleware.call_sync(
                'certificate.query',
                [('id', '=', ad['certificate'])],
                {'get': True}
            )['name']
        with ActiveDirectory_LDAP(ad_conf=ad, logger=self.logger, hosts=dcs) as AD_LDAP:
            ret = AD_LDAP.get_netbios_name()

        if ret and smb['workgroup'] != ret:
            self.logger.debug(f'Updating SMB workgroup to match the short form of the AD domain [{ret}]')
            self.middleware.call_sync('datastore.update', 'services.cifs', smb['id'], {'cifs_srv_workgroup': ret})

        return ret

    @private
    def get_kerberos_servers(self):
        """
        This returns at most 3 kerberos servers located in our AD site. This is to optimize
        kerberos configuration for locations where kerberos servers may span the globe and
        have equal DNS weighting. Since a single kerberos server may represent an unacceptable
        single point of failure, fall back to relying on normal DNS queries in this case.
        """
        ad = self.middleware.call_sync('activedirectory.config')
        AD_DNS = ActiveDirectory_DNS(conf=ad, logger=self.logger)
        krb_kdc = AD_DNS.get_n_working_servers(SRV['KERBEROSDOMAINCONTROLLER'], 3)
        krb_admin_server = AD_DNS.get_n_working_servers(SRV['KERBEROS'], 3)
        krb_kpasswd_server = AD_DNS.get_n_working_servers(SRV['KPASSWD'], 3)
        kdc = [i['host'] for i in krb_kdc]
        admin_server = [i['host'] for i in krb_admin_server]
        kpasswd = [i['host'] for i in krb_kpasswd_server]
        for servers in [kdc, admin_server, kpasswd]:
            if len(servers) == 1:
                return None

        return {'krb_kdc': kdc, 'krb_admin_server': admin_server, 'krb_kpasswd_server': kpasswd}

    @private
    @job(lock='set_ntp_servers')
    def set_ntp_servers(self, job):
        """
        Appropriate time sources are a requirement for an AD environment. By default kerberos authentication
        fails if there is more than a 5 minute time difference between the AD domain and the member server.
        If the NTP servers are the default that we ship the NAS with. If this is the case, then we will
        discover the Domain Controller with the PDC emulator FSMO role and set it as the preferred NTP
        server for the NAS.
        """
        ntp_servers = self.middleware.call_sync('system.ntpserver.query')
        default_ntp_servers = list(filter(lambda x: 'freebsd.pool.ntp.org' in x['address'], ntp_servers))
        if len(ntp_servers) != 3 or len(default_ntp_servers) != 3:
            return

        ad = self.middleware.call_sync('activedirectory.config')
        pdc = ActiveDirectory_DNS(conf=ad, logger=self.logger).get_n_working_servers(SRV['PDC'], 1)
        self.middleware.call_sync('system.ntpserver.create', {'address': pdc[0]['host'], 'prefer': True})

    @private
    def get_site(self):
        """
        First, use DNS to identify domain controllers
        Then, find a domain controller that is listening for LDAP connection if this information is not cached.
        Then, perform an LDAP query to determine our AD site
        """
        ad = self.middleware.call_sync('activedirectory.config')
        i = self.middleware.call_sync('interfaces.query')
        dcs = self.middleware.call_sync('activedirectory._get_cached_srv_records', SRV['DOMAINCONTROLLER'])
        set_new_cache = True if not dcs else False

        if not dcs:
            dcs = ActiveDirectory_DNS(conf=ad, logger=self.logger).get_n_working_servers(SRV['DOMAINCONTROLLER'], 3)
        if not dcs:
            raise CallError('Failed to open LDAP socket to any DC in domain.')

        if set_new_cache:
            self.middleware.call_sync('activedirectory._set_cached_srv_records', SRV['DOMAINCONTROLLER'], ad['site'], dcs)

        if ad['certificate']:
            ad['certificate'] = self.middleware.call_sync(
                'certificate.query',
                [('id', '=', ad['certificate'])],
                {'get': True}
            )['name']
        with ActiveDirectory_LDAP(ad_conf=ad, logger=self.logger, hosts=dcs, interfaces=i) as AD_LDAP:
            site = AD_LDAP.locate_site()

        if not site:
            site = 'Default-First-Site-Name'

        if not ad['site']:
            self.middleware.call_sync(
                'datastore.update',
                'directoryservice.activedirectory',
                ad['id'],
                {'ad_site': site}
            )

        return site

    @accepts(
        Dict(
            'leave_ad',
            Str('username', required=True),
            Str('password', required=True, private=True)
        )
    )
    async def leave(self, data):
        """
        Leave Active Directory domain. This will remove computer
        object from AD and clear relevant configuration data from
        the NAS.
        This requires credentials for appropriately-privileged user.
        Credentials are used to obtain a kerberos ticket, which is
        used to perform the actual removal from the domain.
        """
        ad = await self.config()
        principal = f'{data["username"]}@{ad["domainname"]}'
        smb_ha_mode = await self.middleware.call('smb.get_smb_ha_mode')
        ad_kinit = await Popen(
            ['/usr/bin/kinit', '--renewable', '--password-file=STDIN', principal],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE
        )
        output = await ad_kinit.communicate(input=data['password'].encode())
        if ad_kinit.returncode != 0:
            raise CallError(f"kinit for domain [{ad['domainname']}] with password failed: {output[1].decode()}")

        netads = await run([SMBCmd.NET.value, '-U', data['username'], '-k', 'ads', 'leave'], check=False)
        if netads.returncode != 0:
            raise CallError(f"Failed to leave domain: [{netads.stderr.decode()}]")

        if smb_ha_mode != 'LEGACY':
            krb_princ = await self.middleware.call(
                'kerberos.keytab.query',
                [('name', '=', 'AD_MACHINE_ACCOUNT')],
                {'get': True}
            )
            await self.middleware.call('kerberos.keytab.delete', krb_princ['id'])

        await self.middleware.call('datastore.delete', 'directoryservice.kerberosrealm', ad['kerberos_realm'])
        await self.middleware.call('activedirectory.stop')

        self.logger.debug("Successfully left domain: %s", ad['domainname'])

    @private
    @job(lock='fill_ad_cache')
    def fill_cache(self, job, force=False):
        """
        Use UID2SID and GID2SID entries in Samba's gencache.tdb to populate the AD_cache.
        Since this can include IDs outside of our configured idmap domains (Local accounts
        will also appear here), there is a check to see if the ID is inside the idmap ranges
        configured for domains that are known to us. Some samba idmap backends support
        id_type_both, in which case the will be GID2SID entries for AD users. getent group
        succeeds in this case (even though the group doesn't exist in AD). Since these
        we don't want to populate the UI cache with these entries, try to getpwnam for
        GID2SID entries. If it's an actual group, getpwnam will fail. This heuristic
        may be revised in the future, but we want to keep things as simple as possible
        here since the list of entries numbers perhaps in the tens of thousands.
        """
        if self.middleware.call_sync('cache.has_key', 'AD_cache') and not force:
            raise CallError('AD cache already exists. Refusing to generate cache.')

        self.middleware.call_sync('cache.pop', 'AD_cache')
        ad = self.middleware.call_sync('activedirectory.config')
        smb = self.middleware.call_sync('smb.config')
        id_type_both_backends = [
            'rid',
            'autorid'
        ]
        if not ad['disable_freenas_cache']:
            """
            These calls populate the winbindd cache
            """
            pwd.getpwall()
            grp.getgrall()
        elif ad['bindname']:
            id = subprocess.run(['/usr/bin/id', f"{smb['workgroup']}\\{ad['bindname']}"], capture_output=True)
            if id.returncode != 0:
                self.logger.debug('failed to id AD bind account [%s]: %s', ad['bindname'], id.stderr.decode())

        netlist = subprocess.run(
            [SMBCmd.NET.value, 'cache', 'list'],
            capture_output=True,
            check=False
        )
        if netlist.returncode != 0:
            raise CallError(f'Winbind cache dump failed with error: {netlist.stderr.decode().strip()}')

        known_domains = []
        local_users = {}
        local_groups = {}
        local_users.update({x['uid']: x for x in self.middleware.call_sync('user.query')})
        local_users.update({x['gid']: x for x in self.middleware.call_sync('group.query')})
        cache_data = {'users': {}, 'groups': {}}
        configured_domains = self.middleware.call_sync('idmap.query')
        user_next_index = group_next_index = 300000000
        for d in configured_domains:
            if d['name'] == 'DS_TYPE_ACTIVEDIRECTORY':
                known_domains.append({
                    'domain': smb['workgroup'],
                    'low_id': d['range_low'],
                    'high_id': d['range_high'],
                    'id_type_both': True if d['idmap_backend'] in id_type_both_backends else False,
                })
            elif d['domain'] not in ['DS_TYPE_DEFAULT_DOMAIN', 'DS_TYPE_LDAP']:
                known_domains.append({
                    'domain': d['name'],
                    'low_id': d['range_low'],
                    'high_id': d['range_high'],
                    'id_type_both': True if d['idmap_backend'] in id_type_both_backends else False,
                })

        for line in netlist.stdout.decode().splitlines():
            if line.startswith('Key: IDMAP/UID2SID'):
                cached_uid = int((line.split())[1][14:])
                """
                Do not cache local users. This is to avoid problems where a local user
                may enter into the id range allotted to AD users.
                """
                if local_users.get(cached_uid, None):
                    continue

                for d in known_domains:
                    if cached_uid in range(d['low_id'], d['high_id']):
                        """
                        Samba will generate UID and GID cache entries when idmap backend
                        supports id_type_both.
                        """
                        try:
                            user_data = pwd.getpwuid(cached_uid)
                            cache_data['users'].update({user_data.pw_name: {
                                'id': user_next_index,
                                'uid': user_data.pw_uid,
                                'username': user_data.pw_name,
                                'unixhash': None,
                                'smbhash': None,
                                'group': {},
                                'home': '',
                                'shell': '',
                                'full_name': user_data.pw_gecos,
                                'builtin': False,
                                'email': '',
                                'password_disabled': False,
                                'locked': False,
                                'sudo': False,
                                'microsoft_account': False,
                                'attributes': {},
                                'groups': [],
                                'sshpubkey': None,
                                'local': False,
                                'id_type_both': d['id_type_both']
                            }})
                            user_next_index += 1
                            break
                        except KeyError:
                            break

            if line.startswith('Key: IDMAP/GID2SID'):
                cached_gid = int((line.split())[1][14:])
                if local_groups.get(cached_gid, None):
                    continue

                for d in known_domains:
                    if cached_gid in range(d['low_id'], d['high_id']):
                        """
                        Samba will generate UID and GID cache entries when idmap backend
                        supports id_type_both. Actual groups will return key error on
                        attempt to generate passwd struct. It is also possible that the
                        winbindd cache will have stale or expired entries. Failure on getgrgid
                        should not be fatal here.
                        """
                        try:
                            group_data = grp.getgrgid(cached_gid)
                        except KeyError:
                            break

                        cache_data['groups'].update({group_data.gr_name: {
                            'id': group_next_index,
                            'gid': group_data.gr_gid,
                            'group': group_data.gr_name,
                            'builtin': False,
                            'sudo': False,
                            'users': [],
                            'local': False,
                            'id_type_both': d['id_type_both']
                        }})
                        group_next_index += 1
                        break

        if not cache_data.get('users'):
            return
        sorted_cache = {}
        sorted_cache['users'] = dict(sorted(cache_data['users'].items()))
        sorted_cache['groups'] = dict(sorted(cache_data['groups'].items()))

        self.middleware.call_sync('cache.put', 'AD_cache', sorted_cache)
        self.middleware.call_sync('dscache.backup')

    @private
    async def get_cache(self):
        """
        Returns cached AD user and group information. If proactive caching is enabled
        then this will contain all AD users and groups, otherwise it contains the
        users and groups that were present in the winbindd cache when the cache was
        last filled. The cache expires and is refilled every 24 hours, or can be
        manually refreshed by calling fill_cache(True).
        """
        if not await self.middleware.call('cache.has_key', 'AD_cache'):
            await self.middleware.call('activedirectory.fill_cache')
            self.logger.debug('cache fill is in progress.')
            return {'users': {}, 'groups': {}}
        return await self.middleware.call('cache.get', 'AD_cache')


class WBStatusThread(threading.Thread):
    def __init__(self, **kwargs):
        super(WBStatusThread, self).__init__()
        self.setDaemon(True)
        self.middleware = kwargs.get('middleware')
        self.logger = self.middleware.logger
        self.finished = threading.Event()
        self.state = MSG_WINBIND_ONLINE

    def parse_msg(self, data):
        if data == str(DSStatus.LEAVING.value):
            return

        m = json.loads(data)
        new_state = self.state

        if not self.middleware.call_sync('activedirectory.config')['enable']:
            self.logger.debug('Ignoring winbind message for disabled AD service: [%s]', m)
            return

        try:
            new_state = DSStatus(m['winbind_message']).value
        except Exception as e:
            self.logger.debug('Received invalid winbind status message [%s]: %s', m, e)
            return

        if m['domain_name_netbios'] != self.middleware.call_sync('smb.config')['workgroup']:
            self.logger.debug(
                'Domain [%s] changed state to %s',
                m['domain_name_netbios'],
                DSStatus(m['winbind_message']).name
            )
            return

        if self.state != new_state:
            self.logger.debug(
                'State of domain [%s] transistioned to [%s]',
                m['forest_name'], DSStatus(m['winbind_message'])
            )
            self.middleware.call_sync('activedirectory.set_state', DSStatus(m['winbind_message']))
            if new_state == DSStatus.FAULTED.value:
                self.middleware.call_sync(
                    "alert.oneshot_create",
                    "ActiveDirectoryDomainOffline",
                    {"domain": m["domain_name_netbios"]}
                )
            else:
                self.middleware.call_sync(
                    "alert.oneshot_delete",
                    "ActiveDirectoryDomainOffline",
                    {"domain": m["domain_name_netbios"]}
                )

        self.state = new_state

    def read_messages(self):
        while not self.finished.is_set():
            with open('/var/run/samba4/.wb_fifo') as f:
                data = f.read()
                self.parse_msg(data)

        self.logger.debug('exiting winbind messaging thread')

    def run(self):
        osc.set_thread_name('ad_monitor_thread')
        try:
            self.read_messages()
        except Exception as e:
            self.logger.debug('Failed to run monitor thread %s', e, exc_info=True)

    def setup(self):
        if not os.path.exists('/var/run/samba4/.wb_fifo'):
            os.mkfifo('/var/run/samba4/.wb_fifo')

    def cancel(self):
        """
        Write to named pipe to unblock open() in thread and exit cleanly.
        """
        self.finished.set()
        with open('/var/run/samba4/.wb_fifo', 'w') as f:
            f.write(str(DSStatus.LEAVING.value))


class ADMonitorService(Service):
    class Config:
        private = True

    def __init__(self, *args, **kwargs):
        super(ADMonitorService, self).__init__(*args, **kwargs)
        self.thread = None
        self.initialized = False
        self.lock = threading.Lock()

    def start(self):
        if not self.middleware.call_sync('activedirectory.config')['enable']:
            self.logger.trace('Active directory is disabled. Exiting AD monitoring.')
            return

        with self.lock:
            if self.initialized:
                return

            thread = WBStatusThread(
                middleware=self.middleware,
            )
            thread.setup()
            self.thread = thread
            thread.start()
            self.initialized = True

    def stop(self):
        thread = self.thread
        if thread is None:
            return

        thread.cancel()
        self.thread = None

        with self.lock:
            self.initialized = False

    def restart(self):
        self.stop()
        self.start()


async def setup(middleware):
    """
    During initial boot let smb_configure script start monitoring once samba's
    rundir is created.
    """
    if await middleware.call('system.ready'):
        await middleware.call('admonitor.start')
