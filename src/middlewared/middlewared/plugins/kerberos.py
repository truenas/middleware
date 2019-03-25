import asyncio
import base64
import datetime
import enum
import os
import subprocess
import time
from middlewared.schema import accepts, Any, Bool, Cron, Dict, Int, List, Patch, Path, Str
from middlewared.service import CallError, CRUDService, Service, item_method, private, ValidationErrors
from middlewared.utils import run, Popen

class keytab(enum.Enum):
    SYSTEM = '/etc/krb5.keytab'
    SAMBA = '/var/db/samba4/private/samba.keytab'

class KerberosService(Service):
    """
    :start:  - configures kerberos and performs kinit if needed
    :stop:   - performs kdestroy and clears cached klist output
    :status: - returns false if there is no kerberos tgt or if it is expired 'klist -t'
    :renew:  - compares current time with expiration timestamp in tgt. Issues 'kinit -R' if needed.
               uses cached klist output if available. 
    """

    @private
    async def _klist_test(self):
        klist = await run(['/usr/bin/klist', '-t'], check = False)
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
        ret = False
        ad = await self.middleware.call('activedirectory.config')
        ldap = await self.middleware.call('datastore.config', 'directoryservice.ldap')
        if ad['enable']:
            if ad['kerberos_principal']:
                ad_kinit = await run([ '/usr/bin/kinit', '--renewable', '-t', keytab_file], check=False)
                if ad_kinit.returncode != 0:
                    raise CallError(f"kinit for domain [{ad['domainname']}] with keytab [{keytab_file}] failed: {kinit.stderr.decode()}") 
                ret = True
            else:
                principal = f'{ad["bindname"]}@{ad["domainname"]}'
                ad_kinit = await Popen(
                    ['/usr/bin/kinit', '--renewable', '--password-file=STDIN', principal],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE
                )
                output = await ad_kinit.communicate(input=ad['bindpw'].encode())
                if ad_kinit.returncode != 0:
                    raise CallError(f"kinit for domain [{ad['domainname']}] with password failed: {output[1].decode()}") 
                ret = True

        if ldap['ldap_enable'] and ldap['ldap_realm']:
            if ldap['kerberos_principal']:
                keytab_file = f"/etc/kerberos/{ldap['kerberos_principal']['principal_name']}"
                ad_kinit = await run([ '/usr/bin/kinit', '--renewable', '-t', keytab_file], check=False)
                if ad_kinit.returncode != 0:
                    raise CallError(f"kinit for realm {ldap['realm']} with keytab [{keytab_file}] failed: {kinit.stderr.decode()}") 
                ret = True
            else:
                principal = f'{ldap["bindn"]}'
                self.logger.debug(principal)
                ad_kinit = await Popen(
                    ['/usr/bin/kinit', '--renewable', '--password-file=STDIN', principal],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE
                )
                output = await ad_kinit.communicate(input=ldap['bindpw'].encode())
                if ad_kinit.returncode != 0:
                    raise CallError(f"kinit for realm{ldap['realm']} with password failed: {output[1].decode()}") 
                ret = True

        return ret

    @private
    async def _get_cached_klist(self):
        """
        Try to get retrieve cached kerberos tgt info. If it hasn't been cached,
        perform klist, parse it, put it in cache, then return it. 
        """
        if await self.middleware.call('cache.has_key', 'KRB_TGT_INFO'):
            return (await self.middleware.call('cache.get', 'KRB_TGT_INFO'))
        ad = await self.middleware.call('activedirectory.config')
        ldap = await self.middleware.call('datastore.config', 'directoryservice.ldap')
        ad_TGT = []
        ldap_TGT = []

        if not ad['enable'] and not ldap['ldap_enable']:
            return {'ad_TGT': ad_TGT, 'ldap_TGT': ldap_TGT} 
        if not ad['enable'] and not ldap['ldap_kerberos_realm']:
            return {'ad_TGT': ad_TGT, 'ldap_TGT': ldap_TGT} 

        if not await self.status():
            await self.start()

        try:
            klist = await asyncio.wait_for(
                run(['/usr/bin/klist'], check = False, stdout=subprocess.PIPE), 
                timeout=10.0
            )
            if klist.returncode != 0:
                raise CallError(f'klist failed with error: {klist.stderr.decode()}') 
        except asyncio.TimeoutError:
            self.logger.debug('klist attempt failed after 10 seconds.')
            await self._kdestroy
        klist_output = klist.stdout.decode()
        if klist:
            for line in klist_output.splitlines():
                if ad['enable'] and ad['kerberos_realm']:
                    fields = line.split('  ')
                    if len(fields) == 3 and ad['kerberos_realm']['krb_realm'] in fields[2]:
                        ad_TGT.append({
                            'issued': time.strptime(fields[0], '%b %d %H:%M:%S %Y'),
                            'expires': time.strptime(fields[1], '%b %d %H:%M:%S %Y'),
                            'spn': fields[2]
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

        if must_renew and not must_reinint:
            try:
                kinit = await asyncio.wait_for(run(['/usr/bin/kinit', '-R'], check=False), timeout=15)
                if kinit.returncode != 0:
                    raise CallError(f'kinit -R failed with error: {kinit.stderr.decode()}')
                self.logger.debug(f'Successfully renewed kerberos TGT')
                await self.middleware.call('cache.pop', 'KRB_TGT_INFO')
            except asyncio.TimeoutError:
                self.logger.debug('Attempt to renew kerberos TGT failed after 15 seconds.')
            
        if must_reinit:
            ret = self.start()
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
    async def start(self, realm=None, kinit_timeout = 30):
        """
        kinit can hang because it depends on DNS. If it has not returned within
        30 seconds, it is safe to say that it has failed.
        """
        await self.middleware.call('etc.generate', 'kerberos')
        try:
            ret = await asyncio.wait_for(self._kinit(), timeout=kinit_timeout)
        except asyncio.TimeoutError:
            raise CallError(f'Timed out hung kinit after [{kinit_timeout}] seconds')

class KerberosRealmService(CRUDService):
    """
    Entries for kdc, admin_server, and kpasswd_server are not required.
    If they are unpopulated, then kerberos will use DNS srv records to
    discover the correct servers. The option to hard-code them is provided
    due to AD site discovery. Kerberos has no concept of Active Directory
    sites. This means that middleware performs the site discovery and
    sets the kerberos configuration based on the AD site.
    """

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
        Duplicate kerberos realms should not be allowed (case insensitive), but
        lower-case kerberos realms must be allowed. 
        """
        verrors = ValidationErrors()

        verrors.add_child('kerberos_realm_create', await self._validate(data))

        if verrors:
            raise verrors

        await self.middleware.call('etc.generate', 'kerberos')
        await self.middleware.call('service.restart', 'cron')
        return await self._get_instance(data['id'])

    @accepts(
        Int('id', required=True),
        Dict(
            'kerberos_realm_update',
            Str('realm', required=True),
            List('kdc', default=[]),
            List('admin_server', default=[]),
            List('kpasswd_server', default=[]),
            register=True
        )
    )
    async def do_update(self, id, data):
        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        verrors.add_child('kerberos_realm_update', await self._validate(new))

        if verrors:
            raise verrors

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
        await self.middleware.call('kerberos.start')
        return response

    @accepts(Int("id"))
    async def run(self, id):
        data = await self._get_instance(id)
        await self.middleware.call('etc.generate', 'kerberos')
        await self.middleware.call('kerberos.start')

    @private
    async def _validate(self, data):
        """
        For now validation is limited to checking if we can resolve the hostnames
        configured for the kdc, admin_server, and kpasswd_server can be resolved
        by DNS, and if the realm can be resolved by DNS.
        """
        verrors = ValidationErrors()
        return verrors


class KerberosKeytabService(CRUDService):
    class Config:
        datastore = 'directoryservice.kerberoskeytab'
        datastore_prefix = 'keytab_'
        namespace = 'kerberos.keytab'


    @accepts(
        Dict(
            'kerberos_keytab_create',
            Any('file'),
            Str('name'),
            register=True
        )
    )
    async def do_create(self, data):
        """
        :file: b64encoded kerberos keytab
        """
        verrors = ValidationErrors()

        verrors.add_child('kerberos_principal_create', await self._validate(data))

        if verrors:
            raise verrors

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
            Any('file'),
            Str('name'),
            register=True
        )
    )
    async def do_update(self, id, data):
        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        verrors.add_child('kerberos_principal_update', await self._validate(new))

        if verrors:
            raise verrors

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
        await self.middleware.call("datastore.delete", self._config.datastore, id)
        await self.middleware.call('etc.generate', 'kerberos')
        await self.middleware.call('kerberos.stop')
        await self.middleware.call('kerberos.start')

    @accepts(Int("id"))
    async def run(self, id):
        data = await self._get_instance(id)
        await self.middleware.call('etc.generate', 'kerberos')
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
        keytab_entries = []
        kt_list =  await run(['/usr/sbin/ktutil', '-k', keytab_file, '-v', 'list'], check=False)
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
                        'aliases': fields[4].split() if len(fields)==5 else []
                    })

        return keytab_entries

    @private
    async def _get_nonsamba_principals(self, keytab_list):
        smb = await self.middleware.call('smb.config')
        pruned_list = []
        for i in keytab_list:
            if smb['netbiosname'].upper() not in i['principal'].upper():
                pruned_list.append(i)

        return pruned_list

    @private
    async def _generate_tmp_keytab(self):
         """
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
        for i in to_delete:
            self.logger.debug(i)
            ktutil_remove = await run([
                 '/usr/sbin/ktutil', 
                 '-k', keytab['SAMBA'].value,
                 'remove',
                 '-p', i['principal'], 
                 '-e', i['type']
                 ], check=False
            )
            if ktutil_remove.stderr.decode():
                raise CallError(f"Failed to remove keytab entry from [{keytab['SAMBA'].value}]: {ktutil_remove.stderr.decode()}")
    @private
    async def get_kerberos_principals(self):
        keytab_list = await self._ktutil_list()
        kerberos_principals = []
        for entry in keytab_list:
            if '/' not in entry['principal'] and entry['principal'] not in kerberos_principals:
                kerberos_principals.append(entry['principal'])

        return kerberos_principals

    @private
    async def store_samba_keytab(self):
        """
        Samba will automatically generate system keytab entries for the AD machine account
        (netbios name with '$' appended), and maintain them through machine account password changes.
        Copy the system keytab, parse it, and update the corresponding keytab entry in the freenas configuration
        database.
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

        self.logger.debug(encoded_keytab)
  
        keytabs = await self.query()
        entry = list(filter(lambda x: x['name'] == 'AD_MACHINE_ACCOUNT', keytabs))
        if not entry:
            await self.create({'name': 'AD_MACHINE_ACCOUNT', 'file': encoded_keytab})
        else:
            id = entry[0]['id']
            updated_entry = {'name': 'AD_MACHINE_ACCOUNT', 'file': encoded_keytab}
            await self.update(id, updated_entry)

        return True
