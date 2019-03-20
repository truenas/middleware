import asyncio
import enum
import errno
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


class ActiveDirectory_DNS(object):
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

    def get_domain_controllers(self):
        """
        We will first try fo find DCs based on our AD site. If we don't find
        a DC in our site, then we populate list for whole domain. Ticket #27584
        """
        dcs = []
        if not self.ad['domainname']:
            return dcs

        if self.ad['site']:
            host = f"_ldap._tcp.{self.ad['site']}._sites.dc._msdcs.{self.ad['domainname']}"
        else:
            host = f"_ldap._tcp.dc._msdcs.{self.ad['domainname']}"

        dcs = self._get_SRV_records(host, self.ad['dns_timeout'])

        if not dcs:
            host = f"_ldap._tcp.dc._msdcs.{self.ad['domainname']}"
            dcs = self._get_SRV_records(host, self.ad['dns_timeout'])

        if SSL(self.ad['ssl']) == SSL.USESSL:
            for dc in dcs:
                dc.port = 636

        return dcs

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

    def get_working_domain_controller(self):
        """
        In most situations, the best DC is not required. We only need one that is
        listening.
        """
        dcs = self.get_domain_controllers()
        for dc in dcs:
            host = dc.target.to_text(True)
            port = int(dc.port)
            if self.port_is_listening(host, port, timeout=1):
                return (host, port)


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
        self.ad = kwargs.get('conf')
        self.hosts = kwargs.get('hosts')
        self.logger = kwargs.get('logger')
        self.pagesize = 1024
        self._isopen = False
        self._handle = None
        return

    def __enter__(self):
        return self
    
    def __exit__(self, typ, value, traceback):
        if typ is not None:
            raise

    def _get_uri(self, host):
        if SSL(self.ad['ssl']) == SSL.USESSL:
            proto = "ldaps"
            port = 636
        else:
            proto = "ldap"
            port = 389

        return f"{proto}://{host}:{port}"

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
        if self._isopen:
            return True

        if self.hosts:
            for host in self.hosts:
                uri = self._get_uri(host)
                self.logger.debug(f'URI is {uri}')
                self._handle = ldap.initialize(uri)
                continue

        if self._handle:
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
                    if DS_DEBUG:
                        log.debug("FreeNAS_LDAP_Directory.open: started TLS")

                except ldap.LDAPError as e:
                    raise CallError(e)
            bindname = f"{self.ad['bindname']}@{self.ad['domainname']}"
            try:
                res = self._handle.simple_bind_s(bindname, self.ad['bindpw'])
            except Exception as e:
                raise CallError(e)

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
        self.logger.debug(f'basedn: {basedn}, filter: {filter}')
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

    def _get_rootDSE(self):
        results = self._search('', ldap.SCOPE_BASE, "(objectclass=*)")
        return results

    def _get_rootDN(self):
        results = self._get_rootDSE()
        try:
            results = results[0][1]['rootDomainNamingContext'][0].decode()
        except Exception as e:
            self.logger.debug(f'Failed to get rootDN: [{e}]')
            results = None
        return results

    def _get_baseDN(self):
        results = self._get_rootDSE()
        try:
            results = results[0][1]['defaultNamingContext'][0].decode()
        except Exception as e:
            self.logger.debug(f'Failed to get baseDN: [{e}]')
            results = None
        return results

    def _get_configurationNamingContext(self):
        results = self._get_rootDSE()
        try:
            results = results[0][1]['configurationNamingContext'][0].decode()
        except Exception as e:
            self.logger.debug(f'Failed to get configrationNamingContext: [{e}]')
            results = None
        return results

    def get_netbios_name(self):
        if not self._handle:
            self._open()
        basedn = self._get_baseDN()
        config = self._get_configurationNamingContext()
        self.logger.debug(f'basedn: {basedn}')
        filter = f'(&(objectcategory=crossref)(nCName={basedn}))'
        results = self._search(config, ldap.SCOPE_SUBTREE, filter)
        try:
            netbios_name = results[0][1]['nETBIOSName'][0].decode()

        except Exception as e:
            self._close()
            self.logger.debug(f'Failed to discover short form of domain name: [{e}] res: [{results}]')
            netbios_name = None

        return netbios_name


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
    def validate_credentials(self):
        ret = False
        dcs = []
        ad = self.middleware.call_sync('activedirectory.config')
        with ActiveDirectory_DNS(conf = ad) as AD_DNS:
            dc = AD_DNS.get_working_domain_controller() 
        if not dc:
            raise CallError('Failed to open LDAP socket to any DC in domain.')

        dcs.append(dc[0])
        with ActiveDirectory_LDAP(conf = ad, logger = self.logger, hosts = dcs) as AD_LDAP:
            ret = AD_LDAP.validate_credentials() 
        return ret

    @private
    def get_workgroup(self):
        """
        The 'workgroup' parameter must be set correctly in order for AD join to
        succeed. This is based on the short form of the domain name, which was defined
        by the AD administrator who deployed originally deployed the AD enviornment.
        The only way to reliably get this is to query the LDAP server. This method
        queries and sets it.
        """
        ret = False
        dcs = []
        ad = self.middleware.call_sync('activedirectory.config')
        smb = self.middleware.call_sync('smb.config')
        with ActiveDirectory_DNS(conf = ad) as AD_DNS:
            dc = AD_DNS.get_working_domain_controller() 
        if not dc:
            raise CallError('Failed to open LDAP socket to any DC in domain.')

        dcs.append(dc[0])
        with ActiveDirectory_LDAP(conf = ad, logger = self.logger, hosts = dcs) as AD_LDAP:
            ret = AD_LDAP.get_netbios_name()

        if ret and smb['workgroup'] != ret:
            self.logger.debug(f'Updating SMB workgroup to match the short form of the AD domain [{ret}]')
            self.middleware.call_sync('datastore.update', 'services.cifs', smb['id'], {'cifs_srv_workgroup': ret})
            
        return True 

    @private
    def get_site(self):
        """
        First, use DNS to identify domain controllers
        Then, find a domain controller that is listening for LDAP connection
        Then, perform an LDAP query to determine our AD site 
        """
        ad = self.middleware.call_sync('activedirectory.config')
        with ActiveDirectory_DNS(conf = ad) as AD_DNS:
            dc = AD_DNS.get_working_domain_controller() 

        if not dc:
            raise CallError('Failed to open LDAP socket to any DC in domain.')

        self.logger.debug(dc)

        return str(dc)
