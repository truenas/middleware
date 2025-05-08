import asyncio
import base64
import errno
import gssapi
import os
import subprocess
import tempfile
import time

from middlewared.api import api_method
from middlewared.api.current import (
    KerberosEntry, KerberosRealmEntry, KerberosKeytabEntry,
    KerberosUpdateArgs, KerberosUpdateResult,
    KerberosRealmCreateArgs, KerberosRealmCreateResult,
    KerberosRealmUpdateArgs, KerberosRealmUpdateResult,
    KerberosRealmDeleteArgs, KerberosRealmDeleteResult,
    KerberosKeytabCreateArgs, KerberosKeytabCreateResult,
    KerberosKeytabUpdateArgs, KerberosKeytabUpdateResult,
    KerberosKeytabDeleteArgs, KerberosKeytabDeleteResult,
)
from middlewared.service import CallError, ConfigService, CRUDService, job, periodic, private, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils import run
from middlewared.utils.directoryservices.constants import DSType
from middlewared.utils.directoryservices.krb5_constants import (
    KRB_Keytab,
    krb5ccache,
    KRB_AppDefaults,
    KRB_LibDefaults,
    KRB_ETYPE,
    KRB_TKT_CHECK_INTERVAL,
    PERSISTENT_KEYRING_PREFIX,
    SAMBA_KEYTAB_DIR,
)
from middlewared.utils.directoryservices.krb5 import (
    concatenate_keytab_data,
    gss_get_current_cred,
    gss_acquire_cred_principal,
    gss_acquire_cred_user,
    gss_dump_cred,
    extract_from_keytab,
    keytab_services,
    klist_impl,
    ktutil_list_impl,
    middleware_ccache_path,
    middleware_ccache_type,
    middleware_ccache_uid,
)
from middlewared.utils.directoryservices.krb5_conf import KRB5Conf
from middlewared.utils.directoryservices.krb5_error import KRB5Error
from middlewared.utils.io import write_if_changed


class KerberosModel(sa.Model):
    __tablename__ = 'directoryservice_kerberossettings'

    id = sa.Column(sa.Integer(), primary_key=True)
    ks_appdefaults_aux = sa.Column(sa.Text())
    ks_libdefaults_aux = sa.Column(sa.Text())


class KerberosService(ConfigService):

    class Config:
        service = "kerberos"
        datastore = 'directoryservice.kerberossettings'
        datastore_prefix = "ks_"
        cli_namespace = "directory_service.kerberos.settings"
        role_prefix = 'DIRECTORY_SERVICE'
        entry = KerberosEntry

    @api_method(KerberosUpdateArgs, KerberosUpdateResult, audit='Kerberos configuration update')
    async def do_update(self, data):
        """
        `appdefaults_aux` add parameters to "appdefaults" section of the krb5.conf file.

        `libdefaults_aux` add parameters to "libdefaults" section of the krb5.conf file.
        """
        verrors = ValidationErrors()

        old = await self.config()
        new = old.copy()
        new.update(data)
        verrors.add_child(
            'kerberos_settings_update',
            await self._validate_appdefaults(new['appdefaults_aux'])
        )
        verrors.add_child(
            'kerberos_settings_update',
            await self._validate_libdefaults(new['libdefaults_aux'])
        )
        verrors.check()

        await self.middleware.call(
            'datastore.update', self._config.datastore, old['id'], new,
            {'prefix': self._config.datastore_prefix}
        )

        await self.middleware.call('etc.generate', 'kerberos')
        return await self.config()

    @private
    def generate_stub_config(self, realm, kdc=None, libdefaultsaux=None):
        """
        This method generates a temporary krb5.conf file that is used for the purpose
        of validating credentials and performing domain joins. During the domain join
        process it is important to hard-code a single KDC because our new account may
        not have replicated to other KDCs yet. Once we have joined a domain and inserted
        proper realm configuration this temporary config will be removed by a call
        to etc.generate kerberos.
        """
        aux = libdefaultsaux or []
        krbconf = KRB5Conf()
        libdefaults = {
            str(KRB_LibDefaults.DEFAULT_REALM): realm,
            str(KRB_LibDefaults.DNS_LOOKUP_REALM): 'false',
            str(KRB_LibDefaults.FORWARDABLE): 'true',
            str(KRB_LibDefaults.DEFAULT_CCACHE_NAME): PERSISTENT_KEYRING_PREFIX + '%{uid}'
        }

        realms = [{
            'realm': realm,
            'admin_server': [],
            'kdc': [],
            'kpasswd_server': []
        }]

        if kdc:
            realms[0]['kdc'].append(kdc)
            libdefaults[str(KRB_LibDefaults.DNS_LOOKUP_KDC)] = 'false'
            libdefaults[str(KRB_LibDefaults.DNS_CANONICALIZE_HOSTNAME)] = 'false'

        krbconf.add_libdefaults(libdefaults, '\n'.join(aux))
        krbconf.add_realms(realms)
        krbconf.write()

    @private
    def check_ticket(self, data=None, raise_error=True):
        """
        Perform very basic test that we have a valid kerberos ticket in the
        specified ccache.

        If `raise_error` is set (default), then a CallError is raised with
        errno set to ENOKEY if ticket cannot be read or if ticket is expired.

        returns True if ccache can be read and ticket is not expired, otherwise
        returns False
        """
        ccache_path = middleware_ccache_path(data or {})

        if not isinstance(raise_error, bool):
            raise ValueError(f'{type(raise_error)}: expected bool for raise_error')

        if (cred := gss_get_current_cred(ccache_path, False)) is not None:
            return gss_dump_cred(cred)

        if raise_error:
            raise CallError("Kerberos ticket is required.", errno.ENOKEY)

        return None

    @private
    async def _validate_param_type(self, data):
        supported_validation_types = [
            'boolean',
            'cctype',
            'etypes',
            'keytab',
        ]
        if data['ptype'] not in supported_validation_types:
            return

        if data['ptype'] == 'boolean':
            if data['value'].upper() not in ['YES', 'TRUE', 'NO', 'FALSE']:
                raise CallError(f'[{data["value"]}] is not boolean')

        if data['ptype'] == 'etypes':
            for e in data['value'].split(' '):
                try:
                    KRB_ETYPE(e)
                except Exception:
                    raise CallError(f'[{e}] is not a supported encryption type')

        if data['ptype'] == 'cctype':
            available_types = ['FILE', 'MEMORY', 'DIR']
            if data['value'] not in available_types:
                raise CallError(f'[{data["value"]}] is an unsupported cctype. '
                                f'Available types are {", ".join(available_types)}. '
                                'This parameter is case-sensitive')

        if data['ptype'] == 'keytab':
            try:
                KRB_Keytab(data['value'])
            except Exception:
                raise CallError(f'{data["value"]} is an unsupported keytab path')

    @private
    async def _validate_appdefaults(self, appdefaults):
        verrors = ValidationErrors()
        for line in appdefaults.splitlines():
            param = line.split('=')
            if len(param) == 2 and (param[1].strip())[0] != '{':
                validated_param = list(filter(
                    lambda x: param[0].strip() in (x.value)[0], KRB_AppDefaults
                ))

                if not validated_param:
                    verrors.add(
                        'kerberos_appdefaults',
                        f'{param[0]} is an invalid appdefaults parameter.'
                    )
                    continue

                try:
                    await self._validate_param_type({
                        'ptype': (validated_param[0]).value[1],
                        'value': param[1].strip()
                    })
                except Exception as e:
                    verrors.add(
                        'kerberos_appdefaults',
                        f'{param[0]} has invalid value: {e.errmsg}.'
                    )
                    continue

        return verrors

    @private
    async def _validate_libdefaults(self, libdefaults):
        verrors = ValidationErrors()
        for line in libdefaults.splitlines():
            param = line.split('=')
            if len(param) == 2:
                validated_param = list(filter(
                    lambda x: param[0].strip() in (x.value)[0], KRB_LibDefaults
                ))

                if not validated_param:
                    verrors.add(
                        'kerberos_libdefaults',
                        f'{param[0]} is an invalid libdefaults parameter.'
                    )
                    continue

                try:
                    await self._validate_param_type({
                        'ptype': (validated_param[0]).value[1],
                        'value': param[1].strip()
                    })
                except Exception as e:
                    verrors.add(
                        'kerberos_libdefaults',
                        f'{param[0]} has invalid value: {e.errmsg}.'
                    )

            else:
                verrors.add('kerberos_libdefaults', f'{line} is an invalid libdefaults parameter.')

        return verrors

    @private
    async def get_cred(self, data):
        '''
        Get kerberos cred from directory services config to use for `do_kinit`.
        '''
        conf = data.get('conf', {})
        if not isinstance(conf, dict):
            raise CallError(f'{type(conf)}: expected `conf` key to be dict')

        if conf.get('kerberos_principal'):
            if not isinstance(conf['kerberos_principal'], str):
                raise CallError(f'{type(conf["kerberos_principal"])}: expected string.')

            return {'kerberos_principal': conf['kerberos_principal']}

        if not data.get('dstype'):
            raise CallError('dstype key is required')

        verrors = ValidationErrors()
        dstype = DSType(data['dstype'])
        if dstype is DSType.AD:
            for k in ['bindname', 'bindpw', 'domainname']:
                if not conf.get(k):
                    verrors.add(f'conf.{k}', 'Parameter is required.')

            verrors.check()
            return {
                'username': f'{conf["bindname"]}@{conf["domainname"].upper()}',
                'password': conf['bindpw']
            }

        for k in ['binddn', 'bindpw', 'kerberos_realm']:
            if not conf.get(k):
                verrors.add(f'conf.{k}', 'Parameter is required.')

        verrors.check()
        krb_realm = await self.middleware.call(
            'kerberos.realm.query',
            [('id', '=', conf['kerberos_realm'])],
            {'get': True}
        )
        bind_cn = (conf['binddn'].split(','))[0].split("=")
        return {
            'username': f'{bind_cn[1]}@{krb_realm["realm"]}',
            'password': conf['bindpw']
        }

    @private
    def _dump_current_cred(self, credential, ccache_path):
        """ returns dump of kerberos ccache if valid and not about to expire """
        if (current_cred := gss_get_current_cred(ccache_path, False)) is None:
            return None

        if str(current_cred.name) == credential:
            if current_cred.lifetime > KRB_TKT_CHECK_INTERVAL * 2:
                return gss_dump_cred(current_cred)

        # We need to pass through kdestroy because ccache is in kernel keyring
        kdestroy = subprocess.run(['kdestroy', '-c', ccache_path], check=False, capture_output=True)
        if kdestroy.returncode != 0:
            raise CallError(f'kdestroy failed with error: {kdestroy.stderr.decode()}')

        return None

    @private
    def do_kinit(self, data):
        kinit_options = data.get('kinit-options', {})
        ccache_path = middleware_ccache_path(kinit_options)
        ccache = middleware_ccache_type(kinit_options)
        ccache_uid = middleware_ccache_uid(kinit_options)
        kdc_override = kinit_options.get('kdc_override', {})

        creds = data.get('krb5_cred')
        if not creds:
            raise CallError('krb5_cred is required')

        if not isinstance(creds, dict):
            raise TypeError(f'{type(creds)}: expected dictionary for krb5_cred')

        has_principal = 'kerberos_principal' in creds
        if not has_principal:
            for key in ('username', 'password'):
                if key not in creds:
                    raise CallError(f'{key}: krb5_cred is missing required key')

                if not isinstance(creds[key], str):
                    raise TypeError(f'{type(creds[key])}: {key} in krb5_cred should be str')

        if ccache == krb5ccache.USER:
            if has_principal:
                raise CallError('User-specific ccache not permitted with keytab-based kinit')

            if ccache_uid == 0:
                raise CallError('User-specific ccache not permitted for uid 0')

        if kdc_override.get('kdc'):
            if kdc_override.get('domain') is None:
                raise CallError('Domain missing from KDC override')

            self.generate_stub_config(
                kdc_override.get('domain'),
                kdc_override.get('kdc'),
                kdc_override.get('libdefaults_aux')
            )

        if has_principal:
            principals = self.middleware.call_sync('kerberos.keytab.kerberos_principal_choices')
            if creds['kerberos_principal'] not in principals:
                self.logger.debug('Selected kerberos principal [%s] not available in keytab principals: %s. '
                                  'Regenerating kerberos keytab from configuration file.',
                                  creds['kerberos_principal'], ','.join(principals))
                self.middleware.call_sync('etc.generate', 'kerberos')

            if (current_cred := self._dump_current_cred(creds['kerberos_principal'], ccache_path)) is not None:
                return

            try:
                gss_acquire_cred_principal(
                    creds['kerberos_principal'],
                    ccache_path=ccache_path,
                    lifetime=kinit_options.get('lifetime')
                )
            except gssapi.exceptions.BadNameError:
                raise CallError(
                    f'{creds["kerberos_principal"]}: not a valid kerberos principal name',
                    errno.EINVAL
                )
            except gssapi.exceptions.MissingCredentialsError as exc:
                if exc.min_code & 0xFF:
                    # this is in krb5 lib error table
                    raise KRB5Error(
                        gss_major=exc.maj_code,
                        gss_minor=exc.min_code,
                        errmsg=exc.gen_message()
                    )

                # Error may be in different error table. Convert to CallError
                # for now, but we may special handling in future.
                raise CallError(str(exc))
            except Exception as exc:
                raise CallError(str(exc))
        else:
            if (current_cred := self._dump_current_cred(creds['username'], ccache_path)) is not None:
                # we already have a ticket skip unnecessary ccache manipulation
                return current_cred

            if not creds['password']:
                raise CallError('Password is required')

            try:
                gss_acquire_cred_user(
                    creds['username'],
                    creds['password'],
                    ccache_path=ccache_path,
                    lifetime=kinit_options.get('lifetime')
                )
            except gssapi.exceptions.BadNameError:
                raise CallError(
                    f'{creds["username"]}: not a valid kerberos user name',
                    errno.EINVAL
                )
            except gssapi.exceptions.MissingCredentialsError as exc:
                if exc.min_code & 0xFF:
                    # this is in krb5 lib error table
                    raise KRB5Error(
                        gss_major=exc.maj_code,
                        gss_minor=exc.min_code,
                        errmsg=exc.gen_message()
                    )

                # Error may be in different error table. Convert to CallError
                # for now, but we may special handling in future.
                raise CallError(str(exc))
            except Exception as exc:
                raise CallError(str(exc))

            if ccache == krb5ccache.USER:
                os.chown(ccache_path, ccache_uid, -1)

    @private
    async def _kinit(self):
        """
        For now we only check for kerberos realms explicitly configured in AD and LDAP.
        """
        ad = await self.middleware.call('activedirectory.config')
        ldap = await self.middleware.call('ldap.config')
        await self.middleware.call('etc.generate', 'kerberos')
        payload = {}

        if ad['enable']:
            payload = {
                'dstype': DSType.AD.value,
                'conf': {
                    'bindname': ad['bindname'],
                    'bindpw': ad.get('bindpw', ''),
                    'domainname': ad['domainname'],
                    'kerberos_principal': ad['kerberos_principal'],
                }
            }

        if ldap['enable'] and ldap['kerberos_realm']:
            payload = {
                'dstype': DSType.LDAP.value,
                'conf': {
                    'binddn': ldap['binddn'],
                    'bindpw': ldap['bindpw'],
                    'kerberos_realm': ldap['kerberos_realm'],
                    'kerberos_principal': ldap['kerberos_principal'],
                }
            }

        if not payload:
            return

        cred = await self.get_cred(payload)
        return await self.middleware.call('kerberos.do_kinit', {'krb5_cred': cred})

    @private
    async def klist(self, data=None):
        ccache = middleware_ccache_path(data or {})
        if data:
            timeout = data.get('timeout', 10)
        else:
            timeout = 10

        try:
            return await asyncio.wait_for(
                self.middleware.run_in_thread(klist_impl, ccache),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            raise CallError(f'Attempt to list kerberos tickets timed out after {data["timeout"]} seconds')

    @private
    async def kdestroy(self, data=None):
        ccache = middleware_ccache_path(data or {})

        kdestroy = await run(['kdestroy', '-c', ccache], check=False)
        if kdestroy.returncode != 0:
            raise CallError(f'kdestroy failed with error: {kdestroy.stderr.decode()}')

        return

    @private
    async def stop(self):
        renewal_job = await self.middleware.call(
            'core.get_jobs',
            [['method', '=', 'kerberos.wait_for_renewal'], ['state', '=', 'RUNNING']]
        )
        if renewal_job:
            await self.middleware.call('core.job_abort', renewal_job[0]['id'])

        await self.kdestroy()
        return

    @private
    async def start(self, realm=None, kinit_timeout=30):
        """
        kinit can hang because it depends on DNS. If it has not returned within
        30 seconds, it is safe to say that it has failed.
        """
        await self.middleware.call('etc.generate', 'kerberos')
        try:
            cred = await asyncio.wait_for(self.middleware.create_task(self._kinit()), timeout=kinit_timeout)
        except asyncio.TimeoutError:
            raise CallError(f'Timed out hung kinit after [{kinit_timeout}] seconds')

        await self.middleware.call('kerberos.wait_for_renewal')
        return cred

    @private
    @job(lock="kerberos_renew_watch", transient=True, lock_queue_size=1)
    def wait_for_renewal(self, job):
        while True:
            if (cred := gss_get_current_cred(krb5ccache.SYSTEM.value, raise_error=False)) is None:
                # We don't have kerberos ticket or it has already expired
                # We can redo our kinit
                ds = self.middleware.call_sync('directoryservices.status')
                if ds['type'] is None:
                    self.logger.debug(
                        'Directory services are disabled. Exiting job to wait '
                        'for renewal of kerberos ticket.'
                    )
                    break

                self.logger.debug('Kerberos ticket check failed, getting new ticket')
                self.middleware.call_sync('kerberos.start')

            elif cred.lifetime <= KRB_TKT_CHECK_INTERVAL:
                self.middleware.call_sync('kerberos.start')

            time.sleep(KRB_TKT_CHECK_INTERVAL)


class KerberosRealmModel(sa.Model):
    __tablename__ = 'directoryservice_kerberosrealm'

    id = sa.Column(sa.Integer(), primary_key=True)
    krb_realm = sa.Column(sa.String(120))
    krb_kdc = sa.Column(sa.String(120))
    krb_admin_server = sa.Column(sa.String(120))
    krb_kpasswd_server = sa.Column(sa.String(120))

    __table_args__ = (
        sa.Index("directoryservice_kerberosrealm_krb_realm", "krb_realm", unique=True),
    )


class KerberosRealmService(CRUDService):
    class Config:
        datastore = 'directoryservice.kerberosrealm'
        datastore_prefix = 'krb_'
        datastore_extend = 'kerberos.realm.kerberos_extend'
        namespace = 'kerberos.realm'
        cli_namespace = 'directory_service.kerberos.realm'
        role_prefix = 'DIRECTORY_SERVICE'
        entry = KerberosRealmEntry

    @private
    async def kerberos_extend(self, data):
        for param in ['kdc', 'admin_server', 'kpasswd_server']:
            data[param] = data[param].split(' ') if data[param] else []

        return data

    @private
    async def kerberos_compress(self, data):
        for param in ['kdc', 'admin_server', 'kpasswd_server']:
            data[param] = ' '.join(data[param])

        return data

    @api_method(
        KerberosRealmCreateArgs, KerberosRealmCreateResult,
        audit='Kerberos realm create:',
        audit_extended=lambda data: data['realm']
    )
    async def do_create(self, data):
        """
        Create a new kerberos realm. This will be automatically populated during the
        domain join process in an Active Directory environment. Kerberos realm names
        are case-sensitive, but convention is to only use upper-case.

        Entries for kdc, admin_server, and kpasswd_server are not required.
        If they are unpopulated, then kerberos will use DNS srv records to
        discover the correct servers. The option to hard-code them is provided
        due to AD site discovery. Kerberos has no concept of Active Directory
        sites. This means that middleware performs the site discovery and
        sets the kerberos configuration based on the AD site.
        """
        verrors = ValidationErrors()

        verrors.add_child('kerberos_realm_create', await self._validate(data))

        verrors.check()

        data = await self.kerberos_compress(data)
        id_ = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix}
        )
        await self.middleware.call('etc.generate', 'kerberos')
        await (await self.middleware.call('service.restart', 'cron')).wait(raise_error=True)
        return await self.get_instance(id_)

    @api_method(
        KerberosRealmUpdateArgs, KerberosRealmUpdateResult,
        audit='Kerberos realm update:',
        audit_callback=True
    )
    async def do_update(self, audit_callback, id_, data):
        """
        Update a kerberos realm by id. This will be automatically populated during the
        domain join process in an Active Directory environment. Kerberos realm names
        are case-sensitive, but convention is to only use upper-case.
        """
        old = await self.get_instance(id_)
        audit_callback(old['realm'])
        new = old.copy()
        new.update(data)

        data = await self.kerberos_compress(new)
        id_ = await self.middleware.call(
            'datastore.update', self._config.datastore, id_, new,
            {'prefix': self._config.datastore_prefix}
        )

        await self.middleware.call('etc.generate', 'kerberos')
        return await self.get_instance(id_)

    @api_method(
        KerberosRealmDeleteArgs, KerberosRealmDeleteResult,
        audit='Kerberos realm delete:',
        audit_callback=True
    )
    async def do_delete(self, audit_callback, id_):
        """
        Delete a kerberos realm by ID.
        """
        realm_name = (await self.get_instance(id_))['realm']
        audit_callback(realm_name)
        await self.middleware.call('datastore.delete', self._config.datastore, id_)
        await self.middleware.call('etc.generate', 'kerberos')

    @private
    async def _validate(self, data):
        verrors = ValidationErrors()
        realms = await self.query()
        for realm in realms:
            if realm['realm'].upper() == data['realm'].upper():
                verrors.add('kerberos_realm', f'kerberos realm with name {realm["realm"]} already exists.')
        return verrors


class KerberosKeytabModel(sa.Model):
    __tablename__ = 'directoryservice_kerberoskeytab'

    id = sa.Column(sa.Integer(), primary_key=True)
    keytab_file = sa.Column(sa.EncryptedText())
    keytab_name = sa.Column(sa.String(120), unique=True)


class KerberosKeytabService(CRUDService):
    class Config:
        datastore = 'directoryservice.kerberoskeytab'
        datastore_prefix = 'keytab_'
        namespace = 'kerberos.keytab'
        cli_namespace = 'directory_service.kerberos.keytab'
        role_prefix = 'DIRECTORY_SERVICE'
        entry = KerberosKeytabEntry

    @api_method(
        KerberosKeytabCreateArgs, KerberosKeytabCreateResult,
        audit='Kerberos keytab create:',
        audit_extended=lambda data: data['name']
    )
    async def do_create(self, data):
        """
        Create a kerberos keytab. Uploaded keytab files will be merged with the system
        keytab under /etc/krb5.keytab.

        `file` b64encoded kerberos keytab
        `name` name for kerberos keytab
        """
        verrors = ValidationErrors()

        await self.validate('kerberos_keytab_create', data, verrors)

        verrors.check()

        id_ = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix}
        )
        await self.middleware.call('etc.generate', 'kerberos')

        return await self.get_instance(id_)

    @api_method(
        KerberosKeytabUpdateArgs, KerberosKeytabUpdateResult,
        audit='Kerberos keytab update:',
        audit_callback=True
    )
    async def do_update(self, audit_callback, id_, data):
        """
        Update kerberos keytab by id.
        """
        old = await self.get_instance(id_)
        audit_callback(old['name'])
        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        await self.validate('kerberos_keytab_update', new, verrors, new['id'])

        verrors.check()

        await self.middleware.call(
            'datastore.update', self._config.datastore, id_, new,
            {'prefix': self._config.datastore_prefix}
        )
        await self.middleware.call('etc.generate', 'kerberos')

        return await self.get_instance(id_)

    @api_method(
        KerberosKeytabDeleteArgs, KerberosKeytabDeleteResult,
        audit='Kerberos keytab delete:',
        audit_callback=True
    )
    async def do_delete(self, audit_callback, id_):
        """
        Delete kerberos keytab by id, and force regeneration of
        system keytab.
        """
        kt = await self.get_instance(id_)
        audit_callback(kt['name'])
        if kt['name'] == 'AD_MACHINE_ACCOUNT':
            ad_config = await self.middleware.call('activedirectory.config')
            if ad_config['enable']:
                raise CallError(
                    'Active Directory machine account keytab may not be deleted while '
                    'the Active Directory service is enabled.'
                )

            await self.middleware.call(
                'datastore.update', 'directoryservice.activedirectory',
                ad_config['id'], {'kerberos_principal': ''}, {'prefix': 'ad_'}
            )

        await self.middleware.call('datastore.delete', self._config.datastore, id_)
        await self.middleware.call('etc.generate', 'kerberos')
        await self._cleanup_kerberos_principals()
        await self.middleware.call('kerberos.stop')
        try:
            await self.middleware.call('kerberos.start')
        except Exception as e:
            self.logger.debug(
                'Failed to start kerberos service after deleting keytab entry: %s' % e
            )

    @private
    async def _cleanup_kerberos_principals(self):
        principal_choices = await self.middleware.call('kerberos.keytab.kerberos_principal_choices')
        ad = await self.middleware.call('activedirectory.config')
        ldap = await self.middleware.call('ldap.config')
        if ad['kerberos_principal'] and ad['kerberos_principal'] not in principal_choices:
            await self.middleware.call('activedirectory.update', {'kerberos_principal': ''})
        if ldap['kerberos_principal'] and ldap['kerberos_principal'] not in principal_choices:
            await self.middleware.call('ldap.update', {'kerberos_principal': ''})

    @private
    def _validate_impl(self, schema, data, verrors):
        """
        - synchronous validation -
        For now validation is limited to checking if we can resolve the hostnames
        configured for the kdc, admin_server, and kpasswd_server can be resolved
        by DNS, and if the realm can be resolved by DNS.
        """
        try:
            decoded = base64.b64decode(data['file'])
        except Exception as e:
            verrors.add(f"{schema}.file", f"Keytab is a not a properly base64-encoded string: [{e}]")
            return

        with tempfile.NamedTemporaryFile() as f:
            f.write(decoded)
            f.flush()

            try:
                if not ktutil_list_impl(f.name):
                    verrors.add(f"{schema}.file", "File does not contain any keytab entries")
            except Exception as e:
                verrors.add(f"{schema}.file", f"Failed to validate keytab: [{e}]")

    @private
    async def validate(self, schema, data, verrors, id_=None):
        """
        async wrapper for validate
        """
        await self._ensure_unique(verrors, schema, 'name', data['name'], id_)
        if not data['file']:
            verrors.add(f'{schema}.file', 'base64-encoded keytab file is required')

        return await self.middleware.run_in_thread(self._validate_impl, schema, data, verrors)

    @private
    async def ktutil_list(self, keytab_file=KRB_Keytab['SYSTEM'].value):
        try:
            return await self.middleware.run_in_thread(ktutil_list_impl, keytab_file)
        except Exception as e:
            self.logger.warning("Failed to list kerberos keytab [%s]: %s",
                                keytab_file, e)

        return []

    @private
    async def kerberos_principal_choices(self):
        """
        Keytabs typically have multiple entries for same principal (differentiated by enc_type).
        Since the enctype isn't relevant in this situation, only show unique principal names.

        Return empty list if system keytab doesn't exist.
        """
        if not await self.middleware.run_in_thread(os.path.exists, KRB_Keytab['SYSTEM'].value):
            return []

        kerberos_principals = []

        for entry in await self.ktutil_list():
            if entry['principal'] not in kerberos_principals:
                kerberos_principals.append(entry['principal'])

        return sorted(kerberos_principals)

    @private
    def has_nfs_principal(self):
        """
        This method checks whether the kerberos keytab contains an nfs service principal
        """
        try:
            return 'nfs' in keytab_services(KRB_Keytab.SYSTEM.value)
        except FileNotFoundError:
            return False

    @private
    def store_ad_keytab(self):
        """
        libads automatically generates a system keytab during domain join process. This
        method parses the system keytab and inserts as the AD_MACHINE_ACCOUNT keytab.
        """
        samba_keytabs = []
        for file in os.listdir(SAMBA_KEYTAB_DIR):
            samba_keytabs.append(extract_from_keytab(os.path.join(SAMBA_KEYTAB_DIR, file), []))

        if not samba_keytabs:
            return

        ad = self.middleware.call_sync('activedirectory.config')
        keytab_file = concatenate_keytab_data(samba_keytabs)
        keytab_file_encoded = base64.b64encode(keytab_file).decode()

        entry = self.middleware.call_sync('kerberos.keytab.query', [('name', '=', 'AD_MACHINE_ACCOUNT')])
        if not entry:
            self.middleware.call_sync(
                'datastore.insert', self._config.datastore,
                {'name': 'AD_MACHINE_ACCOUNT', 'file': keytab_file_encoded},
                {'prefix': self._config.datastore_prefix}
            )
        else:
            self.middleware.call_sync(
                'datastore.update', self._config.datastore, entry[0]['id'],
                {'name': 'AD_MACHINE_ACCOUNT', 'file': keytab_file_encoded},
                {'prefix': self._config.datastore_prefix}
            )

        if not ad['kerberos_principal']:
            self.middleware.call_sync('datastore.update', 'directoryservice.activedirectory', 1, {
                'ad_kerberos_principal': f'{ad["netbiosname"]}$@{ad["domainname"]}'
            })

        write_if_changed(KRB_Keytab.SYSTEM.value, keytab_file, perms=0o600)

    @periodic(3600)
    @private
    async def check_updated_keytab(self):
        """
        Check whether keytab needs updating. This currently checks for changes
        to the AD_MACHINE_ACCOUNT keytab due to the possibility that it can be
        changed by user playing around with `net ads` command from shell.

        When this happens, the last_password_change timestamp is altered in
        secrets.tdb and so we can base whether to update that keytab entry
        based on the timestamp rather than trying to evaluate the keytab itself.
        """
        if not await self.middleware.call('system.ready'):
            return

        if (await self.middleware.call('activedirectory.config'))['enable'] is False:
            return

        ts = await self.middleware.call('directoryservices.get_last_password_change')
        if ts['dbconfig'] == ts['secrets']:
            return

        self.logger.debug("Machine account password has changed. Stored copies of "
                          "kerberos keytab and directory services secrets will now "
                          "be updated.")

        await self.middleware.call('directoryservices.secrets.backup')
        await self.middleware.call('kerberos.keytab.store_ad_keytab')
