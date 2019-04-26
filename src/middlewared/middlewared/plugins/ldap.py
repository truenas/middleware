import asyncio
import enum
import errno
import grp
import ldap
import ldap.sasl
import pwd
import socket
import subprocess

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


class LDAPQuery(object):
    def __init__(self, **kwargs):
        super(LDAPQuery, self).__init__()
        self.ldap = kwargs.get('conf')
        self.logger = kwargs.get('logger')
        self.hosts = kwargs.get('hosts')
        self.pagesize = 1024
        self._isopen = False
        self._handle = None
        self._rootDSE = None
        return

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

        SASL GSSAPI bind only succeeds when DNS reverse lookup zone
        is correctly populated. Fall through to simple bind if this
        fails.
        """
        res = None
        if self._isopen:
            return True

        if self.hosts:
            saved_simple_error = None
            saved_gssapi_error = None
            for server in self.hosts:
                proto = 'ldaps' if SSL(self.ldap['ssl']) == SSL.USESSL else 'ldap'
                port = 636 if SSL(self.ldap['ssl']) == SSL.USESSL else 389 
                uri = f"{proto}://{server}:{port}"
                try:
                    self._handle = ldap.initialize(uri)
                except Exception as e:
                    self.logger.debug(f'Failed to initialize ldap connection to [{uri}]: ({e}). Moving to next server.')
                    continue

                res = None
                ldap.protocol_version = ldap.VERSION3
                ldap.set_option(ldap.OPT_REFERRALS, 0)
                ldap.set_option(ldap.OPT_NETWORK_TIMEOUT, 10.0)

                if SSL(self.ldap['ssl']) != SSL.NOSSL:
                    ldap.set_option(ldap.OPT_X_TLS_ALLOW, 1)
                    ldap.set_option(
                        ldap.OPT_X_TLS_CACERTFILE,
                        f"/etc/certificates/{self.ldap['certificate']['cert_name']}.crt"
                    )
                    ldap.set_option(
                        ldap.OPT_X_TLS_REQUIRE_CERT,
                        ldap.OPT_X_TLS_ALLOW
                    )

                if SSL(self.ldap['ssl']) == SSL.USESSL:
                    try:
                        self._handle.start_tls_s()

                    except ldap.LDAPError as e:
                        self.logger.debug('%s', e)

                if self.ldap['anonbind']:
                    try:
                        res = self._handle._handle.simple_bind_s()
                        break
                    except Exception as e:
                        saved_simple_error = e
                        self.logger.debug('Anonymous bind failed: %s' % e)
                        continue

                if self.ldap['kerberos_principal']:
                    try:
                        self._handle.sasl_gssapi_bind_s()
                        res = True
                        break
                    except Exception as e:
                        saved_gssapi_error = e
                        self.logger.debug(f'SASL GSSAPI bind failed: {e}. Attempting simple bind')

                try:
                    res = self._handle.simple_bind_s(self.ldap['binddn'], self.ldap['bindpw'])
                    break
                except Exception as e:
                    self.logger.debug(f'Failed to bind to [{uri}] using [{self.ldap["binddn"]}]: {e}')
                    saved_simple_error = e
                    continue

            if res:
                self._isopen = True
            elif saved_gssapi_error:
                raise CallError(saved_gssapi_error)
            elif saved_simple_error:
                raise CallError(saved_simple_error)

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

    def get_samba_domains(self):
        if not self._handle:
            self._open()
        filter = '(objectclass=sambaDomain)' 
        results = self._search(self.ldap['basedn'], ldap.SCOPE_SUBTREE, filter)
        domains = []
        if results:
            for d in results:
                domains.append(d[1]['sambaDomainName'][0].decode())

        self._close()
        return domains 

    def get_root_DSE(self):
        """
        root DSE query is defined in RFC4512 as a search operation
        with an empty baseObject, scope of baseObject, and a filter of
        "(objectClass=*)"
        In theory this should be accessible with an anonymous bind. In practice,
        it's better to use proper auth because configurations can vary wildly.
        """
        if not self._handle:
            self._open()
        filter = '(objectclass=*)'
        results = self._search('', ldap.SCOPE_BASE, filter)
        dse_objs = []
        for r in results:
            parsed_data = {} 
            for k,v in r[1].items():
                v = list(i.decode() for i in v)
                parsed_data.update({k:v}) 

            dse_objs.append({
                'dn': r[0],
                'data': parsed_data 
            })
        self._close()
        return dse_objs 


class LDAPService(ConfigService):
    class Config:
        service = "ldap"
        datastore = 'directoryservice.ldap'
        datastore_extend = "ldap.ldap_extend"
        datastore_prefix = "ldap_"

    @private
    async def ldap_extend(self, data):
        data['hostname'] = data['hostname'].split()
        return data 

    @private
    async def ldap_compress(self, data):
        data['hostname'] = ','.join(data['hostname'])
        return data 

    @private
    async def ldap_validate(self, ldap):
        port = 636 if SSL(self.ldap['ssl']) == SSL.USESSL else 389
        for h in ldap['hostname']:
            self.middleware.call('ldap.port_is_listening', h, port, ldap['dns_timeout'])
        self.middleware.call('ldap.validate_credentials')

    @accepts(Dict(
        'ldap_update',
        List('hostname', required=True),
        Str('basedn', required=True),
        Str('binddn'),
        Str('bindpw', private=True),
        Bool('anonbind', default=False),
        Str('usersuffix'),
        Str('groupsuffix'),
        Str('passwordsuffix'),
        Str('machinesuffix'),
        Str('sudosuffix'),
        Str('ssl', default='off', enum=['off', 'on', 'start_tls']),
        Int('certificate'),
        Int('timeout', default=30),
        Int('dns_timeout', default=5),
        Str('idmap_backend', default='ldap', enum=['script', 'ldap']),
        Dict(
            'kerberos_realm',
            Int('id'),
            Str('krb_realm'),
            List('krb_kdc'),
            List('krb_admin_server'),
            List('krb_kpasswd_server'),
        ),
        Str('kerberos_principal'),
        Bool('has_samba_schema', default=False),
        Str('auxiliary_parameters', default=False),
        Str('schema', default='rfc2307', enum=['rfc2307', 'rfc2307bis']),
        Bool('enable'),
        update=True
    ))
    async def do_update(self, data):
        """
        Update LDAP Service Configuration.

        """
        must_reload = False
        old = await self.config()
        new = old.copy()
        new.update(data)
        if old != new:
            must_reload = True

        await self.ldap_compress(new)
        await self.middleware.call(
            'datastore.update',
            'directoryservice.ldap',
            old['id'],
            new,
            {'prefix': 'ldap_'}
        )

        if must_reload:
            if new['enable']:
                await self.middleware.call('ldap.start')
            else:
                await self.middleware.call('ldap.stop')

        return await self.config()


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
            raise CallError(e)

        finally:
            s.close()

        return ret

    @private
    def validate_credentials(self, ldap=None):
        ret = False
        if ldap == None:
            ldap = self.middleware.call_sync('ldap.config')

        with LDAPQuery(conf=ldap, logger=self.logger, hosts=ldap['hostname']) as LDAP:
            ret = LDAP.validate_credentials()

        return ret

    @private
    def get_samba_domains(self, ldap=None):
        ret = [] 
        if ldap == None:
            ldap = self.middleware.call_sync('ldap.config')

        with LDAPQuery(conf=ldap, logger=self.logger, hosts=ldap['hostname']) as LDAP:
            ret = LDAP.get_samba_domains()

        return ret


    @private
    def get_root_DSE(self, ldap=None):
        """
        root DSE is defined in RFC4512, and must include the following:

        `namingContexts` naming contexts held in the LDAP sever

        `subschemaSubentry` subschema entries known by the LDAP server

        `altServer` alternative servers in case this one is unavailable

        `supportedExtension` list of supported extended operations

        `supportedControl` list of supported controls

        `supportedSASLMechnaisms` recognized Simple Authentication and Security layers
        (SASL) [RFC4422] mechanisms. 

        `supportedLDAPVersion` LDAP versions implemented by the LDAP server

        In practice, this full data is not returned from many LDAP servers
        """
        ret = []
        if ldap == None:
            ldap = self.middleware.call_sync('ldap.config')

        with LDAPQuery(conf=ldap, logger=self.logger, hosts=ldap['hostname']) as LDAP:
            ret = LDAP.get_root_DSE()

        self.logger.debug(ret)
        return ret

    @private
    async def started(self):
        ldap = await self.config()
        try:
            ret = await asyncio.wait_for(self.middleware.call('ldap.get_root_DSE', ldap),
                                         timeout=ldap['timeout'])
        except asyncio.TimeoutError:
            raise CallError('LDAP status check timed out after %s seconds.' % ldap['timeout'])

        if ret:
            await self.__set_state(DSStatus['HEALTHY'])
        else:
            await self.__set_state(DSStatus['FAULTED'])

        return True if ret else False 
 
    @private
    async def get_workgroup(self, ldap=None):
        ret = None 
        smb = await self.middleware.call('smb.config')
        if ldap == None:
            ldap = await self.config()

        try:
            ret = await asyncio.wait_for(self.middleware.call('ldap.get_samba_domains', ldap),
                                         timeout=ldap['timeout'])
        except asyncio.TimeoutError:
            raise CallError('ldap.get_workgroup timed out after %s seconds.' % ldap['timeout'])

        if len(ret) > 1:
            raise CallError("Multiple Samba Domains detected in LDAP environment: %s", ret)
        self.logger.debug(ret)

        ret = ret[0] if ret else [] 
        self.logger.debug(ret)

        if ret and smb['workgroup'] != ret:
            self.logger.debug(f'Updating SMB workgroup to match the LDAP domain name [{ret}]')
            await self.middleware.call('datastore.update', 'services.cifs', smb['id'], {'cifs_srv_workgroup': ret[0]})

        return ret

    @private
    async def __set_state(self, state):
        await self.middleware.call('cache.put', 'LDAP_State', state.name)

    @accepts()
    async def get_state(self):
        """
        Check the state of the LDAP Directory Service.
        See DSStatus for definitions of return values.
        :DISABLED: Service is not enabled.
        If for some reason, the cache entry indicating Directory Service state
        does not exist, re-run a status check to generate a key, then return it.
        """
        ldap = await self.config()
        if not ldap['enable']:
            return 'DISABLED'
        else:
            try:
                return (await self.middleware.call('cache.get', 'LDAP_State'))
            except KeyError:
                await self.started()
                return (await self.middleware.call('cache.get', 'LDAP_State'))

    @private
    async def nslcd_cmd(self, cmd):
        nslcd = await run(['service', 'nslcd', cmd], check=False)
        if nslcd.returncode != 0:
            raise CallError('nslcd failed to %s with errror: %s' % cmd, nslcd.sterr.decode())

    @private
    async def nslcd_status(self):
        nslcd = await run(['service', 'nslcd', 'onestatus'], check=False)
        return True if nslcd.returncode == 0 else False 

    @private
    async def start(self):
        """
        Refuse to start service if the service is alreading in process of starting or stopping.
        If state is 'HEALTHY' or 'FAULTED', then stop the service first before restarting it to ensure
        that the service begins in a clean state.
        """
        ldap = await self.config()

        ldap_state = await self.middleware.call('ldap.get_state')
        if ldap_state in ['LEAVING', 'JOINING']:
            raise CallError('LDAP state is [%s]. Please wait until directory service operation completes.' % ldap_state)
 
        await self.middleware.call('datastore.update', self._config.datastore, ldap['id'], {'ldap_enable': True})
        if ldap['kerberos_realm']:
            await self.middleware.call('kerberos.start')

        await self.middleware.call('etc.generate', 'rc')
        await self.middleware.call('etc.generate', 'nss')
        await self.middleware.call('etc.generate', 'ldap')
        await self.middleware.call('etc.generate', 'pam')
        has_samba_schema = True if (await self.middleware.call('ldap.get_workgroup')) else False 

        if not await self.nslcd_status():
            await self.nslcd_cmd('onestart')
        else:
            await self.nslcd_cmd('onerestart')

        if has_samba_schema:
            await self.middleware.call('etc.generate', 'smb')
            await self.middleware.call('service.restart', 'smb')

        await self.middleware.call('ldap.fill_ldap_cache')

    @private
    async def stop(self):
        ldap = await self.config()
        await self.middleware.call('datastore.update', self._config.datastore, ldap['id'], {'ldap_enable': False})
        await self.__set_state(DSStatus['LEAVING'])
        await self.middleware.call('etc.generate', 'rc')
        await self.middleware.call('etc.generate', 'nss')
        await self.middleware.call('etc.generate', 'ldap')
        await self.middleware.call('etc.generate', 'pam')
        if ldap['has_samba_schema']:
            await self.middleware.call('etc.generate', 'smb')
            await self.middleware.call('service.restart', 'smb')
        await self.middleware.call('cache.pop', 'LDAP_State')
        await self.nslcd_cmd('onestop')

    @private
    @job(lock='fill_ldap_cache')
    def fill_ldap_cache(self, force=False):
        """
        """
        if self.middleware.call_sync('cache.has_key', 'LDAP_cache') and not force:
            raise CallError('LDAP cache already exists. Refusing to generate cache.')

        self.middleware.call_sync('cache.pop', 'LDAP_cache')
        ldap = self.middleware.call_sync('ldap.config')
        pwd_list = pwd.getpwall()
        grp_list = grp.getgrall()

        local_uid_list = list(u['uid'] for u in self.middleware.call_sync('user.query')) 
        local_gid_list = list(g['gid'] for g in self.middleware.call_sync('group.query'))
        cache_data = {'users': [], 'groups': []}

        for u in pwd_list:
            is_local_user = True if u.pw_uid in local_uid_list else False
            if is_local_user:
                continue

            cache_data['users'].append({
                'name': u.pw_name,
                'uid': u.pw_name,
                'uidNumber': u.pw_uid,
                'gidNumber': u.pw_gid,
                'gecos': u.pw_gecos,
                'homeDirectory': u.pw_dir,
                'loginShell': u.pw_shell,
            })

        for g in grp_list:
            is_local_user = True if g.gr_gid in local_gid_list else False
            if is_local_user:
                continue

            cache_data['groups'].append({
                'name': g.gr_name,
                'group': g.gr_name,
                'gidNumber': g.gr_gid,
                'members': g.gr_mem,
            })

        self.middleware.call_sync('cache.put', 'LDAP_cache', cache_data, 86400)

    @private
    async def get_ldap_cache(self):
        """
        """
        if not await self.middleware.call('cache.has_key', 'LDAP_cache'):
            await self.middleware.run_in_thread(self.fill_ldap_cache)
            self.logger.debug('cache fill is in progress.')
            return {}
        return await self.middleware.call('cache.get', 'LDAP_cache')

    @private
    async def get_ldap_usersorgroups_legacy(self, entry_type='users'):
        """
        Compatibility shim for old django user cache Returns list of pwd.struct_passwd
        for users (or corresponding grp structure for groups in the AD domain.
        """
        ldap_cache = await self.get_ldap_cache()
        if not ldap_cache:
            return []
        
        return ldap_cache[entry_type]

    @private
    def get_uncached_userorgroup_legacy(self, entry_type='users', obj=None):
        try:
            if entry_type == 'users':
                return pwd.getpwnam(obj)
            elif entry_type == 'groups':
                return grp.getgrnam(obj)

        except Exception:
            return None 

    @private
    async def get_ldap_userorgroup_legacy(self, entry_type='users', obj=None):
        """
        Compatibility shim for old django user cache
        Returns cached pwd.struct_passwd or grp.struct_group for user or group specified.
        This is called in gui/common/freenasusers.py
        """
        if entry_type == 'users':
            if await self.middleware.call('user.query', [('username', '=', obj)]):
                return None
        else:
            if await self.middleware.call('group.query', [('group', '=', obj)]):
                return None
                    
        ldap_cache = await self.get_ldap_cache()
        if not ldap_cache:
            await self.middleware.call('ldap.get_uncached_userorgroup_legacy', entry_type, obj)

        ret = list(filter(lambda x: x['name'] == obj, ldap_cache[entry_type]))

        if not ret:
            ret = await self.middleware.call('ldap.get_uncached_userorgroup_legacy', entry_type, obj)
        else:
            ret = ret[0]

        return ret

