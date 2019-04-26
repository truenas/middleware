import asyncio
import base64
import datetime
import enum
import os
import subprocess
import time
from middlewared.schema import accepts, Dict, Int, List, Patch, Str
from middlewared.service import CallError, ConfigService, CRUDService, periodic, private, ValidationErrors
from middlewared.utils import run, Popen


class keytab(enum.Enum):
    SYSTEM = '/etc/krb5.keytab'
    SAMBA = '/var/db/system/samba4/private/samba.keytab'


class KerberosService(ConfigService):
    class Config:
        service = "kerberos"
        datastore = 'directoryservice.kerberossettings'
        datastore_prefix = "ks_"

    @accepts(Dict(
        'kerberos_settings_update',
        Str('appdefaults_aux'),
        Str('libdefaults_aux'),
        update=True
    ))
    async def do_update(self, data):
        """
        :appdefaults_aux: add parameters to "appdefaults" section of the krb5.conf file.
        :libdefautls_aux: add parameters to "libdefaults" section of the krb5.conf file.
        """
        old = await self.config()
        new = old.copy()
        new.update(data)
        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            old['id'],
            new,
            {'prefix': 'ks_'}
        )

        await self.middleware.call('etc.generate', 'kerberos')
        return await self.config()

    @private
    async def _klist_test(self):
        """
        Returns false if there is not a TGT or if the TGT has expired.
        """
        klist = await run(['/usr/bin/klist', '-t'], check=False)
        if klist.returncode != 0:
            return False
        return True

    @private
    async def _kinit(self):
        """
        There are two ways of performing the kinit:
        1) username / password combination. In this case, password must be written
           to file or recieved via STDIN
        2) kerberos keytab.

        For now we only check for kerberos realms explicitly configured in AD and LDAP.
        """
        ad = await self.middleware.call('activedirectory.config')
        ldap = await self.middleware.call('ldap.config')
        await self.middleware.call('etc.generate', 'kerberos')
        if ad['enable']:
            if ad['kerberos_principal']:
                ad_kinit = await run(['/usr/bin/kinit', '--renewable', '-k', ad['kerberos_principal']], check=False)
                if ad_kinit.returncode != 0:
                    raise CallError(f"kinit for domain [{ad['domainname']}] with principal [{ad['kerberos_principal']}] failed: {ad_kinit.stderr.decode()}")
            else:
                principal = f'{ad["bindname"]}@{ad["domainname"]}'
                ad_kinit = await Popen(
                    ['/usr/bin/kinit', '--renewable', '--password-file=STDIN', principal],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE
                )
                output = await ad_kinit.communicate(input=ad['bindpw'].encode())
                if ad_kinit.returncode != 0:
                    raise CallError(f"kinit for domain [{ad['domainname']}] with password failed: {output[1].decode()}")
        if ldap['enable'] and ldap['kerberos_realm']:
            if ldap['kerberos_principal']:
                ldap_kinit = await run(['/usr/bin/kinit', '--renewable', '-k', ldap['kerberos_principal']], check=False)
                if ldap_kinit.returncode != 0:
                    raise CallError(f"kinit for realm {ldap['kerberos_realm']} with keytab failed: {ad_kinit.stderr.decode()}")
            else:
                principal = f'{ldap["bindn"]}'
                ad_kinit = await Popen(
                    ['/usr/bin/kinit', '--renewable', '--password-file=STDIN', principal],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE
                )
                output = await ad_kinit.communicate(input=ldap['bindpw'].encode())
                if ad_kinit.returncode != 0:
                    raise CallError(f"kinit for realm{ldap['kerberos_realm']} with password failed: {output[1].decode()}")

    @private
    async def _get_cached_klist(self):
        """
        Try to get retrieve cached kerberos tgt info. If it hasn't been cached,
        perform klist, parse it, put it in cache, then return it.
        """
        if await self.middleware.call('cache.has_key', 'KRB_TGT_INFO'):
            return (await self.middleware.call('cache.get', 'KRB_TGT_INFO'))
        ad = await self.middleware.call('activedirectory.config')
        ldap = await self.middleware.call('ldap.config')
        ad_TGT = []
        ldap_TGT = []
        if not ad['enable'] and not ldap['enable']:
            return {'ad_TGT': ad_TGT, 'ldap_TGT': ldap_TGT}
        if not ad['enable'] and not ldap['kerberos_realm']:
            return {'ad_TGT': ad_TGT, 'ldap_TGT': ldap_TGT}

        if not await self.status():
            await self.start()

        try:
            klist = await asyncio.wait_for(
                run(['/usr/bin/klist', '-v'], check=False, stdout=subprocess.PIPE),
                timeout=10.0
            )
        except Exception as e:
            await self.stop()
            raise CallError("Attempt to list kerberos tickets failed with error: %s", e)

        if klist.returncode != 0:
            await self.stop()
            raise CallError(f'klist failed with error: {klist.stderr.decode()}')

        klist_output = klist.stdout.decode()
        tkts = klist_output.split('\n\n')
        for tkt in tkts:
            s = tkt.splitlines()
            if len(s) > 4:
                for entry in s:
                    if "Auth time" in entry:
                        issued = time.strptime((entry.split('Auth time: '))[1].lstrip().replace('  ', ' '), '%b %d %H:%M:%S %Y')
                    elif "End time" in entry:
                        expires = time.strptime((entry.split('End time: '))[1].lstrip().replace('  ', ' '), '%b %d %H:%M:%S %Y')
                    elif "Server" in entry:
                        server = (entry.split('Server: '))[1]
                    elif "Client" in entry:
                        client = (entry.split('Client: '))[1]
                    elif 'Ticket etype' in entry:
                        etype = (entry.split('Ticket etype: '))[1]
                    elif 'Ticket flags' in entry:
                        flags = (entry.split('Ticket flags: '))[1].split(',')

                if ad['enable'] and ad['kerberos_realm'] and ad['domainname'] in client:
                    ad_TGT.append({
                        'issued': issued,
                        'expires': expires,
                        'client': client,
                        'server': server,
                        'etype': etype,
                        'flags': flags,
                    })

                elif ldap['enable'] and ldap['kerberos_realm']:
                    if ldap['kerberos_realm']['krb_realm'] in client:
                        ldap_TGT.append({
                            'issued': issued,
                            'expires': expires,
                            'client': client,
                            'server': server,
                            'etype': etype,
                            'flags': flags,
                        })

        if ad_TGT or ldap_TGT:
            await self.middleware.call('cache.put', 'KRB_TGT_INFO', {'ad_TGT': ad_TGT, 'ldap_TGT': ldap_TGT})
        return {'ad_TGT': ad_TGT, 'ldap_TGT': ldap_TGT}

    @private
    async def renew(self):
        """
        Compare timestamp of cached TGT info with current timestamp. If we're within 5 minutes
        of expire time, renew the TGT via 'kinit -R'.
        """
        tgt_info = await self._get_cached_klist()
        ret = True

        must_renew = False
        must_reinit = False
        if not tgt_info['ad_TGT'] and not tgt_info['ldap_TGT']:
            must_reinit = True

        if tgt_info['ad_TGT']:
            permitted_buffer = datetime.timedelta(minutes=5)
            current_time = datetime.datetime.now()
            for entry in tgt_info['ad_TGT']:
                tgt_expiry_time = datetime.datetime.fromtimestamp(time.mktime(entry['expires']))
                delta = tgt_expiry_time - current_time
                if datetime.timedelta(minutes=0) > delta:
                    must_reinit = True
                    break
                if permitted_buffer > delta:
                    must_renew = True
                    break

        if tgt_info['ldap_TGT']:
            permitted_buffer = datetime.timedelta(minutes=5)
            current_time = datetime.datetime.now()
            for entry in tgt_info['ldap_TGT']:
                tgt_expiry_time = datetime.datetime.fromtimestamp(time.mktime(entry['expires']))
                delta = tgt_expiry_time - current_time
                if datetime.timedelta(minutes=0) > delta:
                    must_reinit = True
                    break
                if permitted_buffer > delta:
                    must_renew = True
                    break

        if must_renew and not must_reinit:
            try:
                kinit = await asyncio.wait_for(run(['/usr/bin/kinit', '-R'], check=False), timeout=15)
                if kinit.returncode != 0:
                    raise CallError(f'kinit -R failed with error: {kinit.stderr.decode()}')
                self.logger.debug(f'Successfully renewed kerberos TGT')
                await self.middleware.call('cache.pop', 'KRB_TGT_INFO')
            except asyncio.TimeoutError:
                self.logger.debug('Attempt to renew kerberos TGT failed after 15 seconds.')

        if must_reinit:
            ret = await self.start()
            await self.middleware.call('cache.pop', 'KRB_TGT_INFO')

        return ret

    @private
    async def status(self):
        """
        Experience in production environments has indicated that klist can hang
        indefinitely. Fail if we hang for more than 10 seconds. This should force
        a kdestroy and new attempt to kinit (depending on why we are checking status).
        _klist_test will return false if there is not a TGT or if the TGT has expired.
        """
        try:
            ret = await asyncio.wait_for(self._klist_test(), timeout=10.0)
            return ret
        except asyncio.TimeoutError:
            self.logger.debug('kerberos ticket status check timed out after 10 seconds.')
            return False

    @private
    async def stop(self):
        await self.middleware.call('cache.pop', 'KRB_TGT_INFO')
        kdestroy = await run(['/usr/bin/kdestroy'], check=False)
        if kdestroy.returncode != 0:
            raise CallError(f'kdestroy failed with error: {kdestroy.stderr.decode()}')

        return True

    @private
    async def start(self, realm=None, kinit_timeout=30):
        """
        kinit can hang because it depends on DNS. If it has not returned within
        30 seconds, it is safe to say that it has failed.
        """
        await self.middleware.call('etc.generate', 'kerberos')
        try:
            await asyncio.wait_for(self._kinit(), timeout=kinit_timeout)
        except asyncio.TimeoutError:
            raise CallError(f'Timed out hung kinit after [{kinit_timeout}] seconds')


class KerberosRealmService(CRUDService):
    class Config:
        datastore = 'directoryservice.kerberosrealm'
        datastore_prefix = 'krb_'
        datastore_extend = 'kerberos.realm.kerberos_extend'
        namespace = 'kerberos.realm'

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

    @accepts(
        Dict(
            'kerberos_realm_create',
            Str('realm', required=True),
            List('kdc', default=[]),
            List('admin_server', default=[]),
            List('kpasswd_server', default=[]),
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

        if verrors:
            raise verrors

        data = await self.kerberos_compress(data)
        data["id"] = await self.middleware.call(
            "datastore.insert", self._config.datastore, data,
            {
                "prefix": self._config.datastore_prefix
            },
        )
        await self.middleware.call('etc.generate', 'kerberos')
        await self.middleware.call('service.restart', 'cron')
        return await self._get_instance(data['id'])

    @accepts(
        Int('id', required=True),
        Patch(
            "kerberos_realm_create",
            "kerberos_realm_update",
            ("attr", {"update": True})
        )
    )
    async def do_update(self, id, data):
        """
        Update a kerberos realm by id. This will be automatically populated during the
        domain join process in an Active Directory environment. Kerberos realm names
        are case-sensitive, but convention is to only use upper-case.
        """
        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        verrors.add_child('kerberos_realm_update', await self._validate(new))

        if verrors:
            raise verrors

        data = await self.kerberos_compress(new)
        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id,
            new,
            {'prefix': self._config.datastore_prefix}
        )

        await self.middleware.call('etc.generate', 'kerberos')
        return await self._get_instance(id)

    @accepts(Int('id'))
    async def do_delete(self, id):
        """
        Delete a kerberos realm by ID.
        """
        await self.middleware.call("datastore.delete", self._config.datastore, id)
        await self.middleware.call('etc.generate', 'kerberos')

    @private
    async def _validate(self, data):
        verrors = ValidationErrors()
        realms = await self.query()
        for realm in realms:
            if realm['realm'].upper() == data['realm'].upper():
                verrors.add(f'kerberos_realm', f'kerberos realm with name {realm["realm"]} already exists.')
        return verrors


class KerberosKeytabService(CRUDService):
    class Config:
        datastore = 'directoryservice.kerberoskeytab'
        datastore_prefix = 'keytab_'
        datastore_extend = 'kerberos.keytab.kerberos_keytab_extend'
        namespace = 'kerberos.keytab'

    @private
    async def kerberos_keytab_extend(self, data):
        data['file'] = await self.middleware.call('pwenc.decrypt', data['file'])
        return data

    @private
    async def kerberos_keytab_compress(self, data):
        data['file'] = await self.middleware.call('pwenc.encrypt', data['file'])
        return data

    @accepts(
        Dict(
            'kerberos_keytab_create',
            Str('file'),
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

        if verrors:
            raise verrors

        data = await self.kerberos_keytab_compress(data)
        data["id"] = await self.middleware.call(
            "datastore.insert", self._config.datastore, data,
            {
                "prefix": self._config.datastore_prefix
            },
        )
        await self.middleware.call('etc.generate', 'kerberos')

        return await self._get_instance(data['id'])

    @accepts(
        Int('id', required=True),
        Dict(
            'kerberos_keytab_update',
            Str('file'),
            Str('name'),
            register=True
        )
    )
    async def do_update(self, id, data):
        """
        Update kerberos keytab by id.
        """
        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        verrors.add_child('kerberos_principal_update', await self._validate(new))

        if verrors:
            raise verrors

        data = await self.kerberos_keytab_compress(data)
        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id,
            new,
            {'prefix': self._config.datastore_prefix}
        )
        await self.middleware.call('etc.generate', 'kerberos')

        return await self._get_instance(id)

    @accepts(Int('id'))
    async def do_delete(self, id):
        """
        Delete kerberos keytab by id.
        """
        await self.middleware.call("datastore.delete", self._config.datastore, id)
        await self.middleware.call('etc.generate', 'kerberos')
        await self.middleware.call('kerberos.stop')
        await self.middleware.call('kerberos.start')

    @private
    async def _validate(self, data):
        """
        For now validation is limited to checking if we can resolve the hostnames
        configured for the kdc, admin_server, and kpasswd_server can be resolved
        by DNS, and if the realm can be resolved by DNS.
        """
        verrors = ValidationErrors()
        try:
            base64.b64decode(data['file'])
        except Exception as e:
            verrors.add("kerberos.keytab_create", f"Keytab is a not a properly base64-encoded string: [{e}]")
        return verrors

    @private
    async def _ktutil_list(self, keytab_file=keytab['SYSTEM'].value):
        """
        Parse ktutil output.
        """
        keytab_entries = []
        kt_list = await run(
            ["/usr/sbin/ktutil", "-k", keytab_file, "-v", "list"], check=False
        )
        if kt_list.returncode != 0:
            raise CallError(f'ktutil list for keytab [{keytab_file}] failed with error: {kt_list.stderr.decode()}')
        kt_list_output = kt_list.stdout.decode()
        if kt_list_output:
            for line in kt_list_output.splitlines():
                fields = line.split()
                if len(fields) >= 4 and fields[0] != 'Vno':
                    keytab_entries.append({
                        'kvno': fields[0],
                        'type': fields[1],
                        'principal': fields[2],
                        'date': time.strptime(fields[3], '%Y-%m-%d'),
                        'aliases': fields[4].split() if len(fields) == 5 else []
                    })

        return keytab_entries

    @private
    async def _get_nonsamba_principals(self, keytab_list):
        """
        Generate list of Kerberos principals that are not the AD machine account.
        """
        smb = await self.middleware.call('smb.config')
        pruned_list = []
        for i in keytab_list:
            if smb['netbiosname'].upper() not in i['principal'].upper():
                pruned_list.append(i)

        return pruned_list

    @private
    async def _generate_tmp_keytab(self):
        """
        Generate a temporary keytab to separate out the machine account keytab principal.
        ktutil copy returns 1 even if copy succeeds.
        """
        if os.path.exists(keytab['SAMBA'].value):
            os.remove(keytab['SAMBA'].value)
        kt_copy = await run([
            '/usr/sbin/ktutil', 'copy',
            keytab['SYSTEM'].value,
            keytab['SAMBA'].value],
            check=False
        )
        if kt_copy.stderr.decode():
            raise CallError(f"failed to generate [{keytab['SAMBA'].value}]: {kt_copy.stderr.decode()}")

    @private
    async def _prune_keytab_principals(self, to_delete=[]):
        """
        Delete all keytab entries from the tmp keytab that are not samba entries.
        """
        for i in to_delete:
            ktutil_remove = await run([
                '/usr/sbin/ktutil',
                '-k', keytab['SAMBA'].value,
                'remove',
                '-p', i['principal'],
                '-e', i['type']],
                check=False
            )
            if ktutil_remove.stderr.decode():
                raise CallError(f"ktutil_remove [{keytab['SAMBA'].value}]: {ktutil_remove.stderr.decode()}")

    @private
    async def kerberos_principal_choices(self):
        """
        Keytabs typically have multiple entries for same principal (differentiated by enc_type).
        Since the enctype isn't relevant in this situation, only show unique principal names.
        _ktutil_list() will raise exception if system keytab doesn't exist. In this case, return
        empty list.
        """
        try:
            keytab_list = await self._ktutil_list()
        except Exception as e:
            self.logger.debug('"ktutil list" failed. Generating empty list of kerberos principal choices. Error: %s' % e)
            return []

        kerberos_principals = []
        for entry in keytab_list:
            if entry['principal'] not in kerberos_principals:
                kerberos_principals.append(entry['principal'])

        return sorted(kerberos_principals)

    @private
    async def store_samba_keytab(self):
        """
        Samba will automatically generate system keytab entries for the AD machine account
        (netbios name with '$' appended), and maintain them through machine account password changes.

        Copy the system keytab, parse it, and update the corresponding keytab entry in the freenas configuration
        database.

        The current system kerberos keytab and compare with a cached copy before overwriting it when a new
        keytab is generated through middleware 'etc.generate kerberos'.
        """
        if not os.path.exists(keytab['SYSTEM'].value):
            return False

        encoded_keytab = None
        keytab_list = await self._ktutil_list()
        items_to_remove = await self._get_nonsamba_principals(keytab_list)
        await self._generate_tmp_keytab()
        await self._prune_keytab_principals(items_to_remove)
        with open(keytab['SAMBA'].value, 'rb') as f:
            encoded_keytab = base64.b64encode(f.read())

        if not encoded_keytab:
            self.logger.debug(f"Failed to generate b64encoded version of {keytab['SAMBA'].name}")
            return False

        encrypted_keytab = await self.middleware.call('pwenc.encrypt', encoded_keytab.decode())
        entry = await self.query([('name', '=', 'AD_MACHINE_ACCOUNT')])
        if not entry:
            await self.middleware.call(
                'datastore.insert',
                'directoryservice.kerberoskeytab',
                {'keytab_name': 'AD_MACHINE_ACCOUNT', 'keytab_file': encrypted_keytab}
            )
        else:
            id = entry[0]['id']
            updated_entry = {'keytab_name': 'AD_MACHINE_ACCOUNT', 'keytab_file': encrypted_keytab}
            await self.middleware.call('datastore.update', 'directoryservice.kerberoskeytab', id, updated_entry)

        sambakt = await self.query([('name', '=', 'AD_MACHINE_ACCOUNT')])
        if sambakt:
            return sambakt[0]['id']

    @periodic(3600)
    @private
    async def check_updated_keytab(self):
        """
        Check mtime of current kerberos keytab. If it has changed since last check,
        assume that samba has updated it behind the scenes and that the configuration
        database needs to be updated to reflect the change.
        """
        old_mtime = 0
        ad_state = await self.middleware.call('activedirectory.get_state')
        if ad_state == 'DISABLED' or not os.path.exists(keytab['SYSTEM'].value):
            return
        if await self.middleware.call('cache.has_key', 'KEYTAB_MTIME'):
            old_mtime = await self.middleware.call('cache.get', 'KEYTAB_MTIME')

        new_mtime = (os.stat(keytab['SYSTEM'].value)).st_mtime
        if old_mtime == new_mtime:
            return

        await self.store_samba_keytab()
        self.logger.debug('Updating stored AD machine account kerberos keytab')
        await self.middleware.call(
            'cache.put',
            'KEYTAB_MTIME',
            (os.stat(keytab['SYSTEM'].value)).st_mtime
        )

