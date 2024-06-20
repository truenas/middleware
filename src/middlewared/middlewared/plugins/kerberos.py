import asyncio
import base64
import errno
import io
import os
import shutil
import tempfile
import time

from middlewared.plugins.idmap import DSType
from middlewared.schema import accepts, returns, Dict, Int, List, Patch, Str, OROperator, Password, Ref, Datetime, Bool
from middlewared.service import CallError, ConfigService, CRUDService, job, periodic, private, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils import filter_list, run
from middlewared.utils.directoryservices.krb5_constants import (
    KRB_Keytab,
    krb5ccache,
    krb_tkt_flag,
    KRB_AppDefaults,
    KRB_LibDefaults,
    KRB_ETYPE,
    KRB_TKT_CHECK_INTERVAL,
)
from middlewared.utils.directoryservices.krb5 import (
    check_ticket,
    extract_from_keytab,
    keytab_services,
    klist_impl,
    ktutil_list_impl
)
from middlewared.utils.directoryservices.krb5_conf import KRB5Conf


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

    @accepts(Dict(
        'kerberos_settings_update',
        Str('appdefaults_aux', max_length=None),
        Str('libdefaults_aux', max_length=None),
        update=True
    ))
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
    @accepts(Ref('kerberos-options'))
    async def ccache_path(self, data):
        krb_ccache = krb5ccache[data['ccache']]

        path_out = krb_ccache.value
        if krb_ccache == krb5ccache.USER:
            path_out += str(data['ccache_uid'])

        return path_out

    @private
    def generate_stub_config(self, realm, kdc=None):
        if os.path.exists('/etc/krb5.conf'):
            return

        krbconf = KRB5Conf()
        libdefaults = {
            str(KRB_LibDefaults.DEFAULT_REALM): realm,
            str(KRB_LibDefaults.DNS_LOOKUP_REALM): 'false',
            str(KRB_LibDefaults.DEFAULT_CCACHE_NAME): f'FILE:{krb5ccache.SYSTEM.value}'
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

        krbconf.add_libdefaults(libdefaults)
        krbconf.add_realms(realms)
        krbconf.write()

    @private
    @accepts(
        Dict(
            'kerberos-options',
            Str('ccache', enum=[x.name for x in krb5ccache], default=krb5ccache.SYSTEM.name),
            Int('ccache_uid', default=0),
            register=True,
        ),
        Bool('raise_error', default=True)
    )
    def check_ticket(self, data, raise_error):
        """
        Perform very basic test that we have a valid kerberos ticket in the
        specified ccache.

        If `raise_error` is set (default), then a CallError is raised with
        errno set to ENOKEY if ticket cannot be read or if ticket is expired.

        returns True if ccache can be read and ticket is not expired, otherwise
        returns False
        """
        krb_ccache = krb5ccache[data['ccache']]
        ccache_path = krb_ccache.value
        if krb_ccache is krb5ccache.USER:
            ccache_path += str(data['ccache_uid'])

        if check_ticket(ccache_path, False):
            return True

        if raise_error:
            raise CallError("Kerberos ticket is required.", errno.ENOKEY)

        return False

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
    @accepts(Dict(
        "get-kerberos-creds",
        Str("dstype", required=True, enum=[x.name for x in DSType]),
        OROperator(
            Dict(
                'ad_parameters',
                Str('bindname'),
                Str('bindpw'),
                Str('domainname'),
                Str('kerberos_principal')
            ),
            Dict(
                'ldap_parameters',
                Str('binddn'),
                Str('bindpw'),
                Int('kerberos_realm'),
                Str('kerberos_principal')
            ),
            name='conf',
            required=True
        )
    ))
    async def get_cred(self, data):
        '''
        Get kerberos cred from directory services config to use for `do_kinit`.
        '''
        conf = data.get('conf', {})
        if conf.get('kerberos_principal'):
            return {'kerberos_principal': conf['kerberos_principal']}

        verrors = ValidationErrors()
        dstype = DSType[data['dstype']]
        if dstype is DSType.DS_TYPE_ACTIVEDIRECTORY:
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
    @accepts(Dict(
        'do_kinit',
        OROperator(
            Dict(
                'kerberos_username_password',
                Str('username', required=True),
                Password('password', required=True),
                register=True
            ),
            Dict(
                'kerberos_keytab',
                Str('kerberos_principal', required=True),
            ),
            name='krb5_cred',
            required=True,
        ),
        Patch(
            'kerberos-options',
            'kinit-options',
            ('add', {'name': 'renewal_period', 'type': 'int', 'default': 7}),
            ('add', {'name': 'lifetime', 'type': 'int', 'default': 0}),
            ('add', {
                'name': 'kdc_override',
                'type': 'dict',
                'args': [Str('domain', default=None), Str('kdc', default=None)]
            }),
        )
    ))
    async def do_kinit(self, data):
        ccache = krb5ccache[data['kinit-options']['ccache']]
        creds = data['krb5_cred']
        has_principal = 'kerberos_principal' in creds
        ccache_uid = data['kinit-options']['ccache_uid']
        ccache_path = await self.ccache_path({
            'ccache': data['kinit-options']['ccache'],
            'ccache_uid': data['kinit-options']['ccache_uid']
        })

        if ccache == krb5ccache.USER:
            if has_principal:
                raise CallError('User-specific ccache not permitted with keytab-based kinit')

            if ccache_uid == 0:
                raise CallError('User-specific ccache not permitted for uid 0')

        cmd = ['kinit', '-V', '-r', str(data['kinit-options']['renewal_period']), '-c', ccache_path]
        lifetime = data['kinit-options']['lifetime']

        if lifetime != 0:
            minutes = f'{lifetime}m'
            cmd.extend(['-l', minutes])

        if data['kinit-options']['kdc_override']['kdc'] is not None:
            override = data['kinit-options']['kdc_override']
            if override['domain'] is None:
                raise CallError('Domain missing from KDC override')

            await self.middleware.call(
                'kerberos.generate_stub_config',
                override['domain'], override['kdc']
            )

        if has_principal:
            principals = await self.middleware.call('kerberos.keytab.kerberos_principal_choices')
            if creds['kerberos_principal'] not in principals:
                self.logger.debug('Selected kerberos principal [%s] not available in keytab principals: %s. '
                                  'Regenerating kerberos keytab from configuration file.',
                                  creds['kerberos_principal'], ','.join(principals))
                await self.middleware.call('etc.generate', 'kerberos')

            cmd.extend(['-k', creds['kerberos_principal']])
            kinit = await run(cmd, check=False)
            if kinit.returncode != 0:
                errmsg = kinit.stderr.decode()
                err = errno.EAGAIN if 'Resource temporarily unavailable' in errmsg else errno.EFAULT

                raise CallError(f"kinit with principal [{creds['kerberos_principal']}] "
                                f"failed: {errmsg}", err)
            return

        cmd.append(creds['username'])
        kinit = await run(cmd, input=creds['password'].encode(), check=False)

        if kinit.returncode != 0:
            errmsg = kinit.stderr.decode()
            err = errno.EAGAIN if 'Resource temporarily unavailable' in errmsg else errno.EFAULT
            raise CallError(f"kinit with password failed: {errmsg}", err)

        if ccache == krb5ccache.USER:
            await self.middleware.run_in_thread(os.chown, ccache_path, ccache_uid, -1)

        return

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
                'dstype': DSType.DS_TYPE_ACTIVEDIRECTORY.name,
                'conf': {
                    'bindname': ad['bindname'],
                    'bindpw': ad.get('bindpw', ''),
                    'domainname': ad['domainname'],
                    'kerberos_principal': ad['kerberos_principal'],
                }
            }

        if ldap['enable'] and ldap['kerberos_realm']:
            payload = {
                'dstype': DSType.DS_TYPE_LDAP.name,
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
        await self.do_kinit({'krb5_cred': cred})

    @private
    @accepts(Patch(
        'kerberos-options',
        'klist-options',
        ('add', {'name': 'timeout', 'type': 'int', 'default': 10}),
    ))
    async def klist(self, data):
        ccache = krb5ccache[data['ccache']].value

        try:
            return await asyncio.wait_for(
                self.middleware.run_in_thread(klist_impl, ccache),
                timeout=data['timeout']
            )
        except asyncio.TimeoutError:
            raise CallError(f'Attempt to list kerberos tickets timed out after {data["timeout"]} seconds')

    @private
    async def renew(self):
        if not await self.middleware.call('kerberos.check_ticket', {
            'ccache': krb5ccache.SYSTEM.name
        }, False):
            self.logger.warning('Kerberos ticket is unavailable. Performing kinit.')
            return await self.start()

        tgt_info = await self.klist()
        if not tgt_info:
            return await self.start()

        current_time = time.time()

        ticket = filter_list(
            tgt_info['tickets'],
            [['client', '=', tgt_info['default_principal']], ['server', '^', 'krbtgt']],
            {'get': True}
        )

        remaining = ticket['expires'] - current_time
        if remaining < 0:
            self.logger.warning('Kerberos ticket expired. Performing kinit.')
            return await self.start()

        if remaining > KRB_TKT_CHECK_INTERVAL:
            return tgt_info

        if krb_tkt_flag.RENEWABLE.name not in ticket['flags']:
            self.logger.debug("Kerberos ticket is not renewable. Performing kinit.")
            return await self.start()

        if (2 * KRB_TKT_CHECK_INTERVAL) + current_time > ticket['renew_until']:
            # getting close to time when we can no longer renew. Better to kinit again.
            return await self.start()

        try:
            kinit = await asyncio.wait_for(self.middleware.create_task(run(['kinit', '-R'], check=False)), timeout=15)
            if kinit.returncode != 0:
                raise CallError(f'kinit -R failed with error: {kinit.stderr.decode()}')
        except asyncio.TimeoutError:
            raise CallError('Attempt to renew kerberos TGT failed after 15 seconds.')

        self.logger.debug('Successfully renewed kerberos TGT')
        return await self.klist()

    @private
    @accepts(Ref('kerberos-options'))
    async def kdestroy(self, data):
        kdestroy = await run(['kdestroy', '-c', krb5ccache[data['ccache']].value], check=False)
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
            await asyncio.wait_for(self.middleware.create_task(self._kinit()), timeout=kinit_timeout)
        except asyncio.TimeoutError:
            raise CallError(f'Timed out hung kinit after [{kinit_timeout}] seconds')

        await self.middleware.call('kerberos.wait_for_renewal')
        return await self.klist()

    @private
    @job(lock="kerberos_renew_watch", transient=True, lock_queue_size=1)
    async def wait_for_renewal(self, job):
        klist = await self.klist()

        while True:
            now = time.time()

            ticket = filter_list(
                klist['tickets'],
                [['client', '=', klist['default_principal']], ['server', '^', 'krbtgt']],
                {'get': True}
            )

            timestr = time.strftime("%m/%d/%y %H:%M:%S UTC", time.gmtime(ticket['expires']))
            job.set_description(f'Waiting to renew kerberos ticket. Current ticket expires: {timestr}')

            if (ticket['expires'] - (now + KRB_TKT_CHECK_INTERVAL)) > 0:
                await asyncio.sleep(KRB_TKT_CHECK_INTERVAL)
                klist = await self.klist()
                continue

            klist = await self.renew()


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

    ENTRY = Patch(
        'kerberos_realm_create', 'kerberos_realm_entry',
        ('add', Int('id')),
    )

    @accepts(
        Dict(
            'kerberos_realm_create',
            Str('realm', required=True),
            List('kdc'),
            List('admin_server'),
            List('kpasswd_server'),
            register=True
        )
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
        await self.middleware.call('service.restart', 'cron')
        return await self.get_instance(id_)

    @accepts(
        Int('id', required=True),
        Patch(
            "kerberos_realm_create",
            "kerberos_realm_update",
            ("attr", {"update": True})
        )
    )
    async def do_update(self, id_, data):
        """
        Update a kerberos realm by id. This will be automatically populated during the
        domain join process in an Active Directory environment. Kerberos realm names
        are case-sensitive, but convention is to only use upper-case.
        """
        old = await self.get_instance(id_)
        new = old.copy()
        new.update(data)

        data = await self.kerberos_compress(new)
        id_ = await self.middleware.call(
            'datastore.update', self._config.datastore, id_, new,
            {'prefix': self._config.datastore_prefix}
        )

        await self.middleware.call('etc.generate', 'kerberos')
        return await self.get_instance(id_)

    @accepts(Int('id'))
    async def do_delete(self, id_):
        """
        Delete a kerberos realm by ID.
        """
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

    ENTRY = Patch(
        'kerberos_keytab_create', 'kerberos_keytab_entry',
        ('add', Int('id')),
    )

    @accepts(
        Dict(
            'kerberos_keytab_create',
            Str('file', max_length=None),
            Str('name'),
            register=True
        )
    )
    async def do_create(self, data):
        """
        Create a kerberos keytab. Uploaded keytab files will be merged with the system
        keytab under /etc/krb5.keytab.

        `file` b64encoded kerberos keytab
        `name` name for kerberos keytab
        """
        verrors = ValidationErrors()

        verrors.add_child('kerberos_principal_create', await self._validate(data))

        verrors.check()

        id_ = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix}
        )
        await self.middleware.call('etc.generate', 'kerberos')

        return await self.get_instance(id_)

    @accepts(
        Int('id', required=True),
        Patch(
            'kerberos_keytab_create',
            'kerberos_keytab_update',
        )
    )
    async def do_update(self, id_, data):
        """
        Update kerberos keytab by id.
        """
        old = await self.get_instance(id_)
        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        verrors.add_child('kerberos_principal_update', await self._validate(new))

        verrors.check()

        await self.middleware.call(
            'datastore.update', self._config.datastore, id_, new,
            {'prefix': self._config.datastore_prefix}
        )
        await self.middleware.call('etc.generate', 'kerberos')

        return await self.get_instance(id_)

    @accepts(Int('id'))
    async def do_delete(self, id_):
        """
        Delete kerberos keytab by id, and force regeneration of
        system keytab.
        """
        kt = await self.get_instance(id_)
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

    @accepts(Dict(
        'keytab_data',
        Str('name', required=True),
    ))
    @returns(Ref('kerberos_keytab_entry'))
    @job(lock='upload_keytab', pipes=['input'], check_pipes=True)
    async def upload_keytab(self, job, data):
        """
        Upload a keytab file. This method expects the keytab file to be uploaded using
        the /_upload/ endpoint.
        """
        ktmem = io.BytesIO()
        await self.middleware.run_in_thread(shutil.copyfileobj, job.pipes.input.r, ktmem)
        b64kt = base64.b64encode(ktmem.getvalue())
        return await self.middleware.call('kerberos.keytab.create',
                                          {'name': data['name'], 'file': b64kt.decode()})

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
    def _validate_impl(self, data):
        """
        - synchronous validation -
        For now validation is limited to checking if we can resolve the hostnames
        configured for the kdc, admin_server, and kpasswd_server can be resolved
        by DNS, and if the realm can be resolved by DNS.
        """
        verrors = ValidationErrors()
        try:
            decoded = base64.b64decode(data['file'])
        except Exception as e:
            verrors.add("kerberos.keytab_create", f"Keytab is a not a properly base64-encoded string: [{e}]")
            return verrors

        with tempfile.NamedTemporaryFile() as f:
            f.write(decoded)
            f.flush()

            try:
                ktutil_list_impl(f.name)
            except Exception as e:
                verrors.add("kerberos.keytab_create", f"Failed to validate keytab: [{e}]")

        return verrors

    @private
    async def _validate(self, data):
        """
        async wrapper for validate
        """
        return await self.middleware.run_in_thread(self._validate_impl, data)

    @private
    async def ktutil_list(self, keytab_file=KRB_Keytab['SYSTEM'].value):
        try:
            return await self.middleware.run_in_thread(ktutil_list_impl, keytab_file)
        except Exception as e:
            self.logger.warning("Failed to list kerberos keytab [%s]: %s",
                                keytab_file, e)

        return []

    @accepts(roles=['DIRECTORY_SERVICE_READ'])
    @returns(List(
        'system-keytab',
        items=[
            Dict(
                'keytab-entry',
                Int('slot'),
                Int('kvno'),
                Str('principal'),
                Str('etype'),
                Bool('etype_deprecated'),
                Datetime('date')
            )
        ]
    ))
    async def system_keytab_list(self):
        """
        Returns content of system keytab (/etc/krb5.keytab).
        """
        return await self.ktutil_list()

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
        if not os.path.exists(KRB_Keytab.SYSTEM.value):
            self.logger.warning('System keytab is missing. Unable to extract AD machine account keytab.')
            return

        ad = self.middleware.call_sync('activedirectory.config')
        ad_kt_bytes = extract_from_keytab(KRB_Keytab.SYSTEM.value, [['principal', 'Crin', ad['netbiosname']]])
        keytab_file = base64.b64encode(ad_kt_bytes).decode()

        entry = self.middleware.call_sync('kerberos.keytab.query', [('name', '=', 'AD_MACHINE_ACCOUNT')])
        if not entry:
            self.middleware.call_sync(
                'datastore.insert', self._config.datastore,
                {'name': 'AD_MACHINE_ACCOUNT', 'file': keytab_file},
                {'prefix': self._config.datastore_prefix}
            )
        else:
            self.middleware.call_sync(
                'datastore.update', self._config.datastore, entry[0]['id'],
                {'name': 'AD_MACHINE_ACCOUNT', 'file': keytab_file},
                {'prefix': self._config.datastore_prefix}
            )

        if not ad['kerberos_principal']:
            self.middleware.call_sync('datastore.update', 'directoryservice.activedirectory', 1, {
                'ad_kerberos_principal': f'{ad["netbiosname"]}$@{ad["domainname"]}'
            })

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
