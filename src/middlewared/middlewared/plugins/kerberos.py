import asyncio
import datetime
import subprocess
import time
from middlewared.schema import accepts, Bool, Cron, Dict, Int, List, Patch, Path, Str
from middlewared.service import CallError, CRUDService, Service, item_method, private, ValidationErrors
from middlewared.utils import run, Popen

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
        2) kerberos keytab

        For now we only check for kerberos realms explicitly configured in AD and LDAP. 
        """
        ret = False
        ad = await self.middleware.call('activedirectory.config')
        ldap = await self.middleware.call('datastore.config', 'directoryservice.ldap')
        if ad['enable']:
            if ad['kerberos_principal']:
                keytab_file = f"/etc/kerberos/{ad['kerberos_principal']['principal_name']}"
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
                run(['/usr/bin/klist', '-f'], check = False, stdout=subprocess.PIPE), 
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
                    if len(fields) == 4 and ad['kerberos_realm']['krb_realm'] in fields[3]:
                        ad_TGT.append({
                            'issued': time.strptime(fields[0], '%b %d %H:%M:%S %Y'),
                            'expires': time.strptime(fields[1], '%b %d %H:%M:%S %Y'),
                            'flags': fields[2],
                            'spn': fields[3]
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
        Patch(
            'sharingsmb_create',
            'sharingsmb_update',
            ('attr', {'update': True})
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
