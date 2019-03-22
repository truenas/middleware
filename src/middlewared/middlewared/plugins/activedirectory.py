import asyncio
import enum
import errno
import ipaddr
import ldap
import ldap.sasl
import socket
import subprocess

from dns import resolver
from ldap.controls import SimplePagedResultsControl
from middlewared.schema import accepts, Bool, Dict, Int, List, Str
from middlewared.service import job, private, ConfigService
from middlewared.service_exception import CallError
from middlewared.utils import run


class DSStatus(enum.Enum):
    """
    Following items are used for cache entries indicating the status of the
    Directory Service.
    :FAULTED: Directory Service is enabled, but not HEALTHY.
    :LEAVING: Directory Service is in process of stopping.
    :JOINING: Directory Service is in process of starting.
    :HEALTHY: Directory Service is enabled, and last status check has passed.
    There is no "DISABLED" DSStatus because this is controlled by the "enable" checkbox.
    This is a design decision to avoid conflict between the checkbox and the cache entry.
    """
    FAULTED = 1
    LEAVING = 2
    JOINING = 3
    HEALTHY = 4


class SSL(enum.Enum):
    NOSSL = 'off'
    USESSL = 'on'
    USETLS = 'start_tls'


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
    """
    :get_n_working_servers: often only a few working servers are needed and not the whole
    list available on the domain. This takes the SRV record type and number of servers to get
    as arguments.
    """
    def __init__(self, **kwargs):
        super(ActiveDirectory_DNS, self).__init__()
        self.ad = kwargs.get('conf') 
        self.logger = kwargs.get('logger')
        return

    def __enter__(self):
        return self

    def __exit__(self, typ, value, traceback):
        if typ is not None:
            raise

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

        except Exception as e:
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
            s.close()
            raise CallError(e)

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

        if self.ad['site']:
            if 'msdcs' in srv_prefix.value: 
                parts = srv_prefix.value.split('.')
                srv = '.'.join([parts[0],parts[1]])
                msdcs = '.'.join([parts[2], parts[3]])
                host = f"{srv}.{self.ad['site']}._sites.{msdcs}.{self.ad['domainname']}"
            else:
                host = f"{srv_prefix.value}{self.ad['site']}._sites.{self.ad['domainname']}"
        else:
            host = f"{srv_prefix.value}{self.ad['domainname']}"

        servers = self._get_SRV_records(host, self.ad['dns_timeout'])

        if not servers and self.ad['site']:
            host = f"{srv_prefix.value}{self.ad['domainname']}"
            dcs = self._get_SRV_records(host, self.ad['dns_timeout'])

        if SSL(self.ad['ssl']) == SSL.USESSL:
            for server in servers:
                if server.port == 389:
                    server.port = 636

        return servers
        
    def get_n_working_servers(self, srv=SRV['DOMAINCONTROLLER'], number=1):
        servers = self._get_servers(srv)
        found_servers = []
        for server in servers:
            if len(found_servers) == number:
                continue

            host = server.target.to_text(True)
            port = int(server.port)
            if self.port_is_listening(host, port, timeout=1):
                server_info = {'host': host, 'port': port}
                found_servers.append(server_info)

        if self.ad['verbose_logging']:
            self.logger.debug(f'Request for [{number}] of server type [{srv.name}] returned: {found_servers}')
        return found_servers


class ActiveDirectory_LDAP(object):
    """
    :validate_credentials: simple check to determine whether we can establish
    an ldap session with the credentials that are in the configuration.

    :get_workgroup: returns the short form of the AD domain name. Confusingly
    titled 'nETBIOSName'. Must not be confused with the netbios hostname of the
    server. For this reason, API calls it 'workgroup'.

    :get_site: returns the AD site that the NAS is a member of. AD sites are used
    to break up large domains into managable chunks typically based on physical location.
    Although samba handles AD sites independent of the middleware. We need this
    information to determine which kerberos servers to use in the krb5.conf file to
    avoid communicating with a KDC on the other side of the world.
    """
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
        
        return

    def __enter__(self):
        return self
    
    def __exit__(self, typ, value, traceback):
        if typ is not None:
            raise

    def validate_credentials(self):
        """
        For credential validation we simply open an ldap connection
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
            for server in self.hosts:
                proto = 'ldaps' if SSL(self.ad['ssl']) == SSL.USESSL else 'ldap' 
                uri = f"{proto}://{server['host']}:{server['port']}" 
                try:
                    self._handle = ldap.initialize(uri)
                except Exception as e:
                    self.logger.debug(f'Failed to initialize ldap connection to [{uri}]. Moving to next server.') 
                    continue

                if self.ad['verbose_logging']:
                    self.logger.debug(f'Successfully initialized LDAP server: [{uri}]')

                res = None
                ldap.protocol_version = ldap.VERSION3
                ldap.set_option(ldap.OPT_REFERRALS, 0)
                ldap.set_option(ldap.OPT_NETWORK_TIMEOUT, 10.0)

                if SSL(self.ad['ssl']) != SSL.NOSSL:
                    ldap.set_option(ldap.OPT_X_TLS_ALLOW, 1)
                    if self.certfile:
                        ldap.set_option(
                            ldap.OPT_X_TLS_CACERTFILE,
                            self.certfile
                        )
                    ldap.set_option(
                        ldap.OPT_X_TLS_REQUIRE_CERT,
                        ldap.OPT_X_TLS_ALLOW
                    )

                if SSL(self.ad['ssl']) == SSL.USESSL:
                    try:
                        self._handle.start_tls_s()

                    except ldap.LDAPError as e:
                        raise CallError(e)
                        continue
                bindname = f"{self.ad['bindname']}@{self.ad['domainname']}"
                try:
                    res = self._handle.simple_bind_s(bindname, self.ad['bindpw'])
                    if self.ad['verbose_logging']:
                        self.logger.debug(f'Successfully bound to [{uri}] using [{bindname}]')
                    break 
                except Exception as e:
                    self.logger.debug(f'Failed to bind to [{uri}] using [{bindname}]')
                    continue


            if res:
                self._isopen = True

        return (self._isopen is True)

    def _close(self):
        self._isopen = False
        if self._handle:
            self._handle.unbind()
            self._handle = None

    def _search(self, basedn='', scope=ldap.SCOPE_SUBTREE, filter='', timeout=-1, sizelimit=0):
        if not self._handle:
            self._open


        result = []
        results = []
        serverctrls = None
        clientctrls = None
        paged = SimplePagedResultsControl(
            criticality=False,
            size=self.pagesize,
            cookie=''
        )
        paged_ctrls = { SimplePagedResultsControl.controlType: SimplePagedResultsControl }

        if self.pagesize > 0:
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
        else:
            id = self._handle.search_ext(
                basedn,
                scope,
                filterstr=filter,
                attrlist=attributes,
                attrsonly=attrsonly,
                serverctrls=serverctrls,
                clientctrls=clientctrls,
                timeout=timeout,
                sizelimit=sizelimit
            )

            type = ldap.RES_SEARCH_ENTRY
            while type != ldap.RES_SEARCH_RESULT:
                try:
                    type, data = self._handle.result(id, 0)

                except ldap.LDAPError as e:
                    self._logex(e)
                    break

                results.append(data)

            for i in range(len(results)):
                for entry in results[i]:
                    result.append(entry)

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
            st = ipaddr.IPNetwork(network)
                
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
                    ipv4_addr_obj = ipaddr.IPAddress(alias['address'], version=4)
                    for subnet in subnets['ipv4_subnet_info']:
                        if ipv4_addr_obj in subnet['network']:
                            sinfo = self._get_sites(distinguishedname=subnet['site_dn'])[0]
                            if sinfo and len(sinfo) > 1:
                                ipv4_site = sinfo[1]['cn'][0].decode()
                                break
                        
                if alias['type'] == 'INET6':
                    if ipv6_site is not None:
                        continue
                    ipv6_addr_obj = ipaddr.IPAddress(alias['address'], version=6)
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

class ActiveDirectoryService(ConfigService):
    class Config:
        service = "activedirectory"
        datastore = 'directoryservice.activedirectory'
        datastore_extend = "activedirectory.ad_extend"
        datastore_prefix = "ad_"

    @private
    async def ad_extend(self, ad):
        return ad 

    @private
    async def ad_compress(self, ad):
        return ad 

    @accepts(Dict(
        'nis_update',
        Str('domainname'),
        Str('bindname'),
        Str('bindpw'),
        Int('monitor_frequency'),
        Int('recover_retry'),
        Bool('enable_monitor'),
        Str('ssl'),
        Dict('certificate'),
        Bool('verbose_logging'),
        Bool('unix_extensions'),
        Bool('use_default_domain'),
        Bool('disable_freenas_cache'),
        Str('userdn'),
        Str('groupdn'),
        Str('groupdn'),
        Str('site'),
        Str('dcname'),
        Str('gcname'),
        Dict('kerberos_realm'),
        Dict('kerberos_principal'),
        Int('timeout'),
        Int('dns_timeout'),
        Str('idmap_backend'),
        Str('nss_info'),
        Str('ldap_sasl_wrapping'),
        Bool('enable'),
        update=True
    ))
    async def do_update(self, data):
        must_reload = False
        old = await self.config()
        new = old.copy()
        new.update(data)
        await self.ad_compress(new)
        await self.middleware.call(
            'datastore.update',
            'directoryservice.activedirectory',
            old['id'],
            new,
            {'prefix': 'ad_'}
        )

        return await self.config()

    @private
    async def start(self):
        ad = await self.middleware.call('activedirectory.config')
        smb = await self.middleware.call('smb.config')
        await self.middleware.call('datastore.update', 'directoryservice.activedirectory', ad['id'], {'ad_enable': True})
        await self.middleware.call('etc.generate', 'hostname')
        await self.middleware.call('etc.generate', 'rc')
        if not ad['site']:
            asyncio.wait_for(await self.get_site(), 10)
        if smb['workgroup'] == 'WORKGROUP':
            asyncio.wait_for(await self.get_workgroup(), 10)
        if not ad['kerberos_realm']:
            await self.middleware.call(
                'datastore.insert',
                'directoryservice.kerberosrealm',
                {'krb_realm': ad['domainname'].upper()},
            )

        await self.middleware.call('etc.generate', 'kerberos')
        await self.middleware.call('etc.generate', 'smb')
        #ret = await self.__net_ads('testjoin')
        ret = await self.__net_ads('join')
        if not ret:
            self.logger.debug(f"Test join to {ad['domainname']} failed. Performing domain join.")
            await self.__net_ads('join')

        await self.middleware.call('service.restart', 'smb')
        await self.middleware.call('etc.generate', 'pam')
        await self.middleware.call('etc.generate', 'nss')
        return True

    @private
    def validate_credentials(self):
        ret = False
        ad = self.middleware.call_sync('activedirectory.config')
        with ActiveDirectory_DNS(conf = ad, logger = self.logger) as AD_DNS:
            dcs = AD_DNS.get_n_working_servers(SRV['DOMAINCONTROLLER'], 3) 
        if not dc:
            raise CallError('Failed to open LDAP socket to any DC in domain.')

        with ActiveDirectory_LDAP(ad_conf = ad, logger = self.logger, hosts = dcs) as AD_LDAP:
            ret = AD_LDAP.validate_credentials() 
        
        return ret

    @private
    async def get_cached_srv_records(self, srv=SRV['DOMAINCONTROLLER']):
        """
        Avoid unecessary DNS lookups. These can potentially be expensive if DNS
        is flaky. Try site-specific results first, then try domain-wide ones.
        """
        servers = []
        if self.middleware.call('cache.key_exists', f'SRVCACHE_{srv.name}_SITE'):
            servers = self.middleware.call('cache.get', f'SRVCACHE_{srv.name}_SITE') 

        if not servers and self.middleware.call('cache.key_exists', f'SRVCACHE_{srv.name}'):
            servers = self.middleware.call('cache.get', f'SRVCACHE_{srv.name}') 

        return servers

    @private
    async def net_ads(self, command):
        ad = await self.config()
        netads = await run([
            'net', '-k', '-U', 'AD01\administrator', '-d', '10', 
            'ads', command, 
            ad['domainname'], 
            '-S', 'DC01.AD01.LAB.IXSYSTEMS.COM'],
            check = False
        ) 
        if netads.returncode != 0:
            self.logger.debug(f"command net -k ads failed with error: [{netads.stderr.decode().strip()}]")
            if command == 'join':
                raise CallError(f'Failed to join [{ad["domainname"]}]: [{netads.stdout.decode().strip()}]')
            return False

        return True

    @private
    async def get_workgroup(self):
        """
        The 'workgroup' parameter must be set correctly in order for AD join to
        succeed. This is based on the short form of the domain name, which was defined
        by the AD administrator who deployed originally deployed the AD enviornment.
        The only way to reliably get this is to query the LDAP server. This method
        queries and sets it.
        """

        ret = False
        ad = await self.middleware.call('activedirectory.config')
        smb = await self.middleware.call('smb.config')
        with ActiveDirectory_DNS(conf = ad, logger=self.logger) as AD_DNS:
            dcs = AD_DNS.get_n_working_servers(SRV['DOMAINCONTROLLER'], 3) 
        if not dcs:
            raise CallError('Failed to open LDAP socket to any DC in domain.')

        with ActiveDirectory_LDAP(ad_conf=ad, logger=self.logger, hosts = dcs) as AD_LDAP:
            ret = AD_LDAP.get_netbios_name()

        if ret and smb['workgroup'] != ret:
            self.logger.debug(f'Updating SMB workgroup to match the short form of the AD domain [{ret}]')
            await self.middleware.call('datastore.update', 'services.cifs', smb['id'], {'cifs_srv_workgroup': ret})
            
        return True 

    @private
    async def get_site(self):
        """
        First, use DNS to identify domain controllers
        Then, find a domain controller that is listening for LDAP connection
        Then, perform an LDAP query to determine our AD site 
        """
        ad = await self.middleware.call('activedirectory.config')
        i = await self.middleware.call('interfaces.query')
        with ActiveDirectory_DNS(conf = ad, logger=self.logger) as AD_DNS:
            dcs = AD_DNS.get_n_working_servers(SRV['DOMAINCONTROLLER'], 3) 
        if not dcs:
            raise CallError('Failed to open LDAP socket to any DC in domain.')

        with ActiveDirectory_LDAP(ad_conf=ad, logger=self.logger, hosts = dcs, interfaces = i) as AD_LDAP:
            ret = AD_LDAP.locate_site()

        if ret and not ad['site']:
            await self.middleware.call(
                'datastore.update',
                'directoryservice.activedirectory', 
                ad['id'], 
                {'ad_site': ret}
        )

        return True 
