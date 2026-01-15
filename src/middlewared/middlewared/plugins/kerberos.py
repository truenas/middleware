import asyncio
import base64
import errno
import os
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
from middlewared.utils.directoryservices.credential import kinit_with_cred
from middlewared.utils.directoryservices.krb5_constants import (
    KRB_Keytab,
    krb5ccache,
    KRB_TKT_CHECK_INTERVAL,
    SAMBA_KEYTAB_DIR,
)
from middlewared.utils.directoryservices.krb5 import (
    concatenate_keytab_data,
    gss_get_current_cred,
    gss_dump_cred,
    extract_from_keytab,
    keytab_services,
    klist_impl,
    ktutil_list_impl,
    middleware_ccache_path,
)
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
        old = await self.config()
        new = old.copy()
        new.update(data)

        await self.middleware.call(
            'datastore.update', self._config.datastore, old['id'], new,
            {'prefix': self._config.datastore_prefix}
        )

        await self.middleware.call('etc.generate', 'kerberos')
        return await self.config()

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
    async def kinit(self):
        ds_config = await self.middleware.call('directoryservices.config')
        if not ds_config['enable']:
            raise CallError('Directory services are disabled')

        if not ds_config['credential']['credential_type'].startswith('KERBEROS_'):
            raise CallError(
                'Directory services are not configured to use kerberos credentials'
            )

        # Generate our kerberos configuration prior to kinit
        await self.middleware.call('etc.generate', 'kerberos')
        await self.middleware.run_in_thread(kinit_with_cred, ds_config['credential'])

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
            cred = await asyncio.wait_for(self.middleware.create_task(self.kinit()), timeout=kinit_timeout)
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
    krb_primary_kdc = sa.Column(sa.String(120), nullable=True)
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
        await (await self.middleware.call('service.control', 'RESTART', 'cron')).wait(raise_error=True)
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

        ds_realm = (await self.middleware.call('directoryservices.config'))['kerberos_realm']
        if realm_name == ds_realm:
            raise CallError(f'{realm_name}: kerberos realm is used by directory services configuration')

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
        ds_config = await self.middleware.call('directoryservices.config')
        if kt['name'] == 'AD_MACHINE_ACCOUNT':
            if ds_config['enable'] and ds_config['service_type'] == 'ACTIVEDIRECTORY':
                raise CallError(
                    'Active Directory machine account keytab may not be deleted while '
                    'the Active Directory service is enabled.'
                )

            if ds_config['service_type'] == 'ACTIVEDIRECTORY':
                if ds_config['credential']['credential_type'] == 'KERBEROS_PRINCIPAL':
                    # remove credential reference
                    await self.middleware.call('datastore.update', 'directoryservices', ds_config['id'], {
                        'cred_type': None, 'cred_krb5': None
                    })

        if kt['name'] == 'IPA_MACHINE_ACCOUNT':
            if ds_config['enable'] and ds_config['service_type'] == 'IPA':
                raise CallError(
                    'IPA machine account keytab may not be deleted while '
                    'the IPA directory service is enabled.'
                )

            if ds_config['service_type'] == 'IPA':
                if ds_config['credential']['credential_type'] == 'KERBEROS_PRINCIPAL':
                    # remove credential reference
                    await self.middleware.call('datastore.update', 'directoryservices', ds_config['id'], {
                        'cred_type': None, 'cred_krb5': None
                    })

        await self.middleware.call('datastore.delete', self._config.datastore, id_)
        await self.middleware.call('etc.generate', 'kerberos')
        await self.middleware.call('kerberos.stop')
        if ds_config['enable']:
            try:
                await self.middleware.call('kerberos.start')
            except Exception as e:
                self.logger.debug(
                    'Failed to start kerberos service after deleting keytab entry: %s' % e
                )

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

        ds_config = self.middleware.call_sync('directoryservices.config')
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

        netbiosname = self.middleware.call_sync('smb.config')['netbiosname'].upper()
        machine_acct = f'{netbiosname}$@{ds_config["configuration"]["domain"]}'

        ds_cred = ds_config['credential']
        if ds_cred['credential_type'] != 'KERBEROS_PRINCIPAL' or ds_cred['principal'] != machine_acct:
            krb_cred = {
                'credential_type': 'KERBEROS_PRINCIPAL',
                'principal': machine_acct
            }
            self.middleware.call_sync('datastore.update', 'directoryservices', ds_config['id'], {
                'cred_type': 'KERBEROS_PRINCIPAL',
                'cred_krb5': krb_cred
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

        if not await self.middleware.call('failover.is_single_master_node'):
            return

        ds_config = await self.middleware.call('directoryservices.config')
        if not ds_config['enable'] or ds_config['service_type'] != 'ACTIVEDIRECTORY':
            return

        ts = await self.middleware.call('directoryservices.get_last_password_change')
        if ts['dbconfig'] == ts['secrets']:
            return

        self.logger.debug("Machine account password has changed. Stored copies of "
                          "kerberos keytab and directory services secrets will now "
                          "be updated.")

        await self.middleware.call('directoryservices.secrets.backup')
        await self.middleware.call('kerberos.keytab.store_ad_keytab')
