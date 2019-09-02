import asyncio
import enum
import errno
import fcntl
import grp
import ldap
import ldap.sasl
import os
import pwd
import socket
import struct
import sys

from ldap.controls import SimplePagedResultsControl
from middlewared.schema import accepts, Bool, Dict, Int, List, Str
from middlewared.service import job, private, ConfigService, ValidationError
from middlewared.service_exception import CallError
from middlewared.utils import run

_int32 = struct.Struct('!i')


class DSStatus(enum.Enum):
    DISABLED = 0
    FAULTED = 1
    LEAVING = 2
    JOINING = 3
    HEALTHY = 4


class SSL(enum.Enum):
    NOSSL = 'OFF'
    USESSL = 'ON'
    USETLS = 'START_TLS'


class NlscdConst(enum.Enum):
    NSLCD_CONF_PATH = '/usr/local/etc/nslcd.conf'
    NSLCD_PIDFILE = '/var/run/nslcd.pid'
    NSLCD_SOCKET = '/var/run/nslcd/nslcd.ctl'
    NSLCD_VERSION = 0x00000002
    NSLCD_ACTION_STATE_GET = 0x00010002
    NSLCD_RESULT_BEGIN = 1
    NSLCD_RESULT_END = 2


class NslcdClient(object):
    def __init__(self, action):
        # set up the socket (store in class to avoid closing it)
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        fcntl.fcntl(self.sock, fcntl.F_SETFD, fcntl.FD_CLOEXEC)
        # connect to nslcd
        self.sock.connect(NlscdConst.NSLCD_SOCKET.value)
        # self.sock.setblocking(1)
        self.fp = os.fdopen(self.sock.fileno(), 'r+b', 0)
        # write a request header with a request code
        self.action = action
        self.write_int32(NlscdConst.NSLCD_VERSION.value)
        self.write_int32(action)

    def write(self, value):
        self.fp.write(value)

    def write_int32(self, value):
        self.write(_int32.pack(value))

    def write_bytes(self, value):
        self.write_int32(len(value))
        self.write(value)

    def read(self, size):
        value = b''
        while len(value) < size:
            data = self.fp.read(size - len(value))
            if not data:
                raise IOError('NSLCD protocol cut short')
            value += data
        return value

    def read_int32(self):
        return _int32.unpack(self.read(_int32.size))[0]

    def read_bytes(self):
        return self.read(self.read_int32())

    def read_string(self):
        value = self.read_bytes()
        if sys.version_info[0] >= 3:
            value = value.decode('utf-8')
        return value

    def get_response(self):
        # complete the request if required and check response header
        if self.action:
            # flush the stream
            self.fp.flush()
            # read and check response version number
            if self.read_int32() != NlscdConst.NSLCD_VERSION.value:
                raise IOError('NSLCD protocol error')
            if self.read_int32() != self.action:
                raise IOError('NSLCD protocol error')
            # reset action to ensure that it is only the first time
            self.action = None
        # get the NSLCD_RESULT_* marker and return it
        return self.read_int32()

    def close(self):
        if hasattr(self, 'fp'):
            try:
                self.fp.close()
            except IOError:
                pass

    def __del__(self):
        self.close()


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

                if SSL(self.ldap['ssl']) == SSL.USETLS:
                    try:
                        self._handle.start_tls_s()

                    except ldap.LDAPError as e:
                        self.logger.debug('Encountered error initializing start_tls: %s', e)
                        saved_simple_error = e
                        continue

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
                raise CallError(str(saved_gssapi_error))
            elif saved_simple_error:
                raise CallError(str(saved_simple_error))

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

    def parse_results(self, results):
        res = []
        for r in results:
            parsed_data = {}
            for k, v in r[1].items():
                try:
                    v = list(i.decode() for i in v)
                except Exception:
                    v = list(str(i) for i in v)
                parsed_data.update({k: v})

            res.append({
                'dn': r[0],
                'data': parsed_data
            })

        return res

    def get_samba_domains(self):
        """
        This returns a list of configured samba domains on the LDAP
        server. This is used to determine whether the LDAP server has
        The Samba LDAP schema. In this case, the SMB service can be
        configured to use Samba's ldapsam passdb backend.
        """
        if not self._handle:
            self._open()
        filter = '(objectclass=sambaDomain)'
        results = self._search(self.ldap['basedn'], ldap.SCOPE_SUBTREE, filter)
        return self.parse_results(results)

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
        return self.parse_results(results)

    def get_dn(self, dn):
        if not self._handle:
            self._open()
        filter = '(objectclass=*)'
        results = self._search(dn, ldap.SCOPE_SUBTREE, filter)
        return self.parse_results(results)


class LDAPService(ConfigService):
    class Config:
        service = "ldap"
        datastore = 'directoryservice.ldap'
        datastore_extend = "ldap.ldap_extend"
        datastore_prefix = "ldap_"

    @private
    async def ldap_extend(self, data):
        data['hostname'] = data['hostname'].split(',')
        for key in ["ssl", "idmap_backend", "schema"]:
            data[key] = data[key].upper()

        for key in ["certificate", "kerberos_realm"]:
            if data[key] is not None:
                data[key] = data[key]["id"]

        return data

    @private
    async def ldap_compress(self, data):
        data['hostname'] = ','.join(data['hostname'])
        for key in ["ssl", "idmap_backend", "schema"]:
            data[key] = data[key].lower()

        if not data['bindpw']:
            data.pop('bindpw')

        return data

    @private
    async def ldap_validate(self, ldap):
        port = 636 if SSL(ldap['ssl']) == SSL.USESSL else 389
        for h in ldap['hostname']:
            await self.middleware.call('ldap.port_is_listening', h, port, ldap['dns_timeout'])
        await self.middleware.call('ldap.validate_credentials')

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
        Str('ssl', default='OFF', enum=['OFF', 'ON', 'START_TLS']),
        Int('certificate', null=True),
        Bool('disable_freenas_cache'),
        Int('timeout', default=30),
        Int('dns_timeout', default=5),
        Str('idmap_backend', default='LDAP', enum=['SCRIPT', 'LDAP']),
        Int('kerberos_realm', null=True),
        Str('kerberos_principal'),
        Bool('has_samba_schema', default=False),
        Str('auxiliary_parameters', default=False, max_length=None),
        Str('schema', default='RFC2307', enum=['RFC2307', 'RFC2307BIS']),
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
            if new['enable']:
                try:
                    await self.middleware.call('ldap.ldap_validate', new)
                except Exception as e:
                    raise ValidationError('ldap_update', str(e))

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
        if ldap is None:
            ldap = self.middleware.call_sync('ldap.config')

        with LDAPQuery(conf=ldap, logger=self.logger, hosts=ldap['hostname']) as LDAP:
            ret = LDAP.validate_credentials()

        return ret

    @private
    def get_samba_domains(self, ldap=None):
        ret = []
        if ldap is None:
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
        if ldap is None:
            ldap = self.middleware.call_sync('ldap.config')

        with LDAPQuery(conf=ldap, logger=self.logger, hosts=ldap['hostname']) as LDAP:
            ret = LDAP.get_root_DSE()

        return ret

    @private
    def get_dn(self, dn=None, ldap=None):
        """
        Outputs contents of specified DN in JSON. By default will target the basedn.
        """
        ret = []
        if ldap is None:
            ldap = self.middleware.call_sync('ldap.config')

        if dn is None:
            dn = ldap['basedn']
        with LDAPQuery(conf=ldap, logger=self.logger, hosts=ldap['hostname']) as LDAP:
            ret = LDAP.get_dn(dn)

        return ret

    @private
    async def started(self):
        if not (await self.config())['enable']:
            await self.__set_state(DSStatus['DISABLED'])
            return False

        ldap = await self.config()

        try:
            await asyncio.wait_for(self.middleware.call('ldap.get_root_DSE', ldap),
                                   timeout=ldap['timeout'])
        except asyncio.TimeoutError:
            await self.__set_state(DSStatus['FAULTED'])
            raise CallError(f'LDAP status check timed out after {ldap["timeout"]} seconds.', errno.ETIMEDOUT)

        except Exception as e:
            await self.__set_state(DSStatus['FAULTED'])
            raise CallError(e)

        await self.__set_state(DSStatus['HEALTHY'])

        return True

    @private
    async def get_workgroup(self, ldap=None):
        ret = None
        smb = await self.middleware.call('smb.config')
        if ldap is None:
            ldap = await self.config()

        try:
            ret = await asyncio.wait_for(self.middleware.call('ldap.get_samba_domains', ldap),
                                         timeout=ldap['timeout'])
        except asyncio.TimeoutError:
            raise CallError(f'ldap.get_workgroup timed out after {ldap["timeout"]} seconds.', errno.ETIMEDOUT)

        if len(ret) > 1:
            raise CallError(f'Multiple Samba Domains detected in LDAP environment: {ret}', errno.EINVAL)

        ret = ret[0]['data']['sambaDomainName'][0] if ret else []

        if ret and smb['workgroup'] != ret:
            self.logger.debug(f'Updating SMB workgroup to match the LDAP domain name [{ret}]')
            await self.middleware.call('datastore.update', 'services.cifs', smb['id'], {'cifs_srv_workgroup': ret})

        return ret

    @private
    async def __set_state(self, state):
        await self.middleware.call('cache.put', 'LDAP_State', state.name)

    @private
    def get_nslcd_status(self):
        """
        Returns internal nslcd state. nslcd will preferentially use the first LDAP server,
        and only failover if the current LDAP server is unreachable.
        """
        ctx = NslcdClient(NlscdConst.NSLCD_ACTION_STATE_GET.value)
        while ctx.get_response() == NlscdConst.NSLCD_RESULT_BEGIN.value:
            nslcd_status = ctx.read_string()

        ctx.close()
        return nslcd_status

    @accepts()
    async def get_state(self):
        """
        `DISABLED` Directory Service is disabled.

        `FAULTED` Directory Service is enabled, but not HEALTHY. Review logs and generated alert
        messages to debug the issue causing the service to be in a FAULTED state.

        `LEAVING` Directory Service is in process of stopping.

        `JOINING` Directory Service is in process of starting.

        `HEALTHY` Directory Service is enabled, and last status check has passed.
        """
        try:
            return (await self.middleware.call('cache.get', 'LDAP_State'))
        except KeyError:
            try:
                await self.started()
            except Exception:
                pass

        return (await self.middleware.call('cache.get', 'LDAP_State'))

    @private
    async def nslcd_cmd(self, cmd):
        nslcd = await run(['service', 'nslcd', cmd], check=False)
        if nslcd.returncode != 0:
            raise CallError(f'nslcd failed to {cmd} with errror: {nslcd.stderr.decode()}', errno.EFAULT)

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
            raise CallError(f'LDAP state is [{ldap_state}]. Please wait until directory service operation completes.', errno.EBUSY)

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
            await self.middleware.call('smb.store_ldap_admin_password')
            await self.middleware.call('service.restart', 'cifs')

        await self.middleware.call('ldap.fill_cache')

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
            await self.middleware.call('service.restart', 'cifs')
        await self.middleware.call('cache.pop', 'LDAP_State')
        await self.middleware.call('cache.pop', 'LDAP_cache')
        await self.nslcd_cmd('onestop')

    @private
    @job(lock='fill_ldap_cache')
    def fill_cache(self, job, force=False):
        user_next_index = group_next_index = 100000000
        cache_data = {'users': {}, 'groups': {}}

        if self.middleware.call_sync('cache.has_key', 'LDAP_cache') and not force:
            raise CallError('LDAP cache already exists. Refusing to generate cache.')

        self.middleware.call_sync('cache.pop', 'LDAP_cache')

        if (self.middleware.call_sync('ldap.config'))['disable_freenas_cache']:
            self.middleware.call_sync('cache.put', 'LDAP_cache', cache_data)
            self.logger.debug('LDAP cache is disabled. Bypassing cache fill.')
            return

        pwd_list = pwd.getpwall()
        grp_list = grp.getgrall()

        local_uid_list = list(u['uid'] for u in self.middleware.call_sync('user.query'))
        local_gid_list = list(g['gid'] for g in self.middleware.call_sync('group.query'))

        for u in pwd_list:
            is_local_user = True if u.pw_uid in local_uid_list else False
            if is_local_user:
                continue

            cache_data['users'].update({u.pw_name: {
                'id': user_next_index,
                'uid': u.pw_uid,
                'username': u.pw_name,
                'unixhash': None,
                'smbhash': None,
                'group': {},
                'home': '',
                'shell': '',
                'full_name': u.pw_gecos,
                'builtin': False,
                'email': '',
                'password_disabled': False,
                'locked': False,
                'sudo': False,
                'microsoft_account': False,
                'attributes': {},
                'groups': [],
                'sshpubkey': None,
                'local': False
            }})
            user_next_index += 1

        for g in grp_list:
            is_local_user = True if g.gr_gid in local_gid_list else False
            if is_local_user:
                continue

            cache_data['groups'].update({g.gr_name: {
                'id': group_next_index,
                'gid': g.gr_gid,
                'group': g.gr_name,
                'builtin': False,
                'sudo': False,
                'users': [],
                'local': False
            }})
            group_next_index += 1

        self.middleware.call_sync('cache.put', 'LDAP_cache', cache_data)
        self.middleware.call_sync('dscache.backup')

    @private
    async def get_cache(self):
        if not await self.middleware.call('cache.has_key', 'LDAP_cache'):
            await self.middleware.call('ldap.fill_cache')
            self.logger.debug('cache fill is in progress.')
            return {'users': {}, 'groups': {}}
        return await self.middleware.call('cache.get', 'LDAP_cache')
