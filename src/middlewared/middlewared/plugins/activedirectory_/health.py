import errno
import subprocess
import wbclient

from base64 import b64decode
from middlewared.plugins.smb import SMBCmd
from middlewared.plugins.activedirectory_.dns import SRV
from middlewared.schema import accepts, Bool, returns
from middlewared.service import private, Service, ValidationErrors
from middlewared.service_exception import CallError, MatchNotFound
from middlewared.plugins.directoryservices import DSStatus
from middlewared.plugins.idmap_.utils import WBClient, WBCErr
from middlewared.utils import filter_list


class ActiveDirectoryService(Service):

    class Config:
        service = "activedirectory"
        datastore = "directoryservice.activedirectory"

    @private
    def winbind_status(self, check_trust=False):
        try:
            if check_trust:
                return WBClient().check_trust()
            else:
                return WBClient().ping_dc()
        except wbclient.WBCError as e:
            raise CallError(str(e), WBCErr[e.error_code], e.error_code)

    @private
    def check_machine_account_keytab(self, dc):
        if self.middleware.call_sync('kerberos.keytab.query', [['name', '=', 'AD_MACHINE_ACCOUNT']]):
            # For now we will short-circuit if user has an AD_MACHINE_ACCOUNT
            return

        # Use net command to build a kerberos keytab from our stored secrets
        results = subprocess.run(['net', 'ads', 'keytab', 'create'], check=False, capture_output=True)
        if results.returncode != 0:
            raise CallError('Failed to generate kerberos keytab from stored secrets: {results.stderr.decode()}')

        self.middleware.call_sync('kerberos.keytab.store_ad_keytab')

    @private
    def check_machine_account_secret(self, dc):
        """
        Check that the machine account password stored in /var/db/system/samba4/secrets.tdb
        is valid and try some basic recovery if file is missing or lacking entry.

        Validation is performed by extracting the machine account password from secrets.tdb
        and using it to perform a temporary kinit.
        """
        ad_config = self.middleware.call_sync('activedirectory.config')
        smb_config = self.middleware.call_sync('smb.config')

        # retrieve the machine account password from secrets.tdb
        try:
            machine_pass = self.middleware.call_sync(
                'directoryservices.secrets.get_machine_secret',
                smb_config['workgroup']
            )
        except FileNotFoundError:
            # our secrets.tdb file has been deleted for some reason
            # unfortunately sometimes users do this when trying to debug issues
            if not self.middleware.call_sync('directoryservices.secrets.restore', smb_config['netbiosname']):
                raise CallError(
                    'File containing AD machine account password has been removed without a viable '
                    'candidate for restoration. Full rejoin of active directory will be required.'
                )

            machine_pass = self.middleware.call_sync(
                'directoryservices.secrets.get_machine_secret',
                smb_config['workgroup']
            )
        except MatchNotFound:
            # secrets.tdb file exists but lacks an entry for our machine account. This is unrecoverable and so
            # we need to try restoring from backup
            if not self.middleware.call_sync('directoryservices.secrets.restore', smb_config['netbiosname']):
                raise CallError(
                    'Stored AD machine account password has been removed without a viable '
                    'candidate for restoration. Full rejoin of active directory will be required.'
                )

            machine_pass = self.middleware.call_sync(
                'directoryservices.secrets.get_machine_secret',
                smb_config['workgroup']
            )

        # By this point we will have some sort of password (b64encoded)
        cred = self.middleware.call_sync('kerberos.get_cred', {
            'dstype': 'DS_TYPE_ACTIVEDIRECTORY',
            'conf': {
                'bindname': smb_config['netbiosname'].upper() + '$',
                'bindpw': b64decode(machine_pass).decode(),
                'domainname': ad_config['domainname']
            }
        })

        # Actual validation of secret will happen here
        self.middleware.call_sync('kerberos.do_kinit', {
            'krb5_cred': cred,
            'kinit-options': {'ccache': 'TEMP', 'kdc_override': {
                'domain': ad_config['domainname'].upper(),
                'kdc': dc
            }}
        })

        try:
            self.middleware.call_sync('kerberos.kdestroy', {'ccache': 'TEMP'})
        except Exception:
            self.logger.debug("Failed to destroy temporary ccache", exc_info=True)

    @private
    def machine_account_status(self, dc=None):
        def parse_result(data, out):
            if ':' not in data:
                return

            key, value = data.split(':', 1)
            if key not in out:
                # This is not a line we're interested in
                return

            if type(out[key]) == list:
                out[key].append(value.strip())
            elif out[key] == -1:
                out[key] = int(value.strip())
            else:
                out[key] = value.strip()

            return

        cmd = [SMBCmd.NET.value, '-P', 'ads', 'status']
        if dc:
            cmd.extend(['-S', dc])

        results = subprocess.run(cmd, capture_output=True)
        if results.returncode != 0:
            raise CallError(
                'Failed to retrieve machine account status: '
                f'{results.stderr.decode().strip()}'
            )

        output = {
            'userAccountControl': -1,
            'objectSid': None,
            'sAMAccountName': None,
            'dNSHostName': None,
            'servicePrincipalName': [],
            'msDS-SupportedEncryptionTypes': -1
        }

        for line in results.stdout.decode().splitlines():
            parse_result(line, output)

        return output

    @private
    def validate_domain(self, data=None):
        """
        Methods used to determine AD domain health.
        First we check whether our clock offset has grown to potentially production-impacting
        levels, then we change whether another DC in our AD site is able to take over if the
        DC winbind is currently connected to becomes inaccessible.
        """
        domain_info = self.middleware.call_sync('activedirectory.domain_info')
        if abs(domain_info['Server time offset']) > 180:
            raise CallError(
                'Time offset from Active Directory domain exceeds maximum '
                'permitted value. This may indicate an NTP misconfiguration.'
            )

        self.check_machine_account_secret(domain_info['KDC server'])
        self.check_machine_account_keytab(domain_info['KDC server'])
        self.conn_check(data)

    @private
    def conn_check(self, data=None, dc=None):
        """
        Temporarily connect to netlogon share of a DC that isn't the one that
        winbind is currently communicating with in order to validate our credentials
        and ability to failover in case of outage on winbind's current DC.

        We only check a single DC because domains can have a significantly large number
        of domain controllers in a given site.
        """
        def get_dc(ad):
            found_dc = None
            res = self.middleware.call_sync(
                'activedirectory.get_n_working_servers',
                ad['domainname'],
                SRV.DOMAINCONTROLLER.name,
                ad['site'],
                2,
                ad['dns_timeout'],
                ad['verbose_logging']
            )
            if len(res) == 0:
                self.logger.debug("No results")
                return found_dc

            if len(res) == 1:
                self.logger.warning("Less than two Domain Controllers are in our "
                                    "Active Directory Site. This may result in production "
                                    "outage if the currently connected DC is unreachable.")

                return res[0]['host']

            """
            In some pathologically bad cases attempts to get the DC that winbind is currently
            communicating with can time out. For this particular health check, the winbind
            error should not be considered fatal.
            """
            try:
                our_dc = self.winbind_status()
                other_dcs = filter_list(res, [['host', 'C!=', our_dc]])
                if other_dcs:
                    found_dc = other_dcs[0]['host']
            except Exception:
                self.logger.warning("Failed to retrieve current DC.", exc_info=True)
                found_dc = res[0]['host']

            return found_dc

        if data is None:
            data = self.middleware.call_sync("activedirectory.config")

        to_check = dc or get_dc(data)
        if to_check is None:
            raise CallError('Failed to find connectable Domain Controller')

        # TODO: evaluate  UAC to determine account status
        self.machine_account_status(dc)

    @accepts(roles=['DIRECTORY_SERVICE_READ'])
    @returns(Bool('started'))
    async def started(self):
        """
        Issue a no-effect command to our DC. This checks if our secure channel connection to our
        domain controller is still alive. It has much less impact than wbinfo -t.
        Default winbind request timeout is 60 seconds, and can be adjusted by the smb4.conf parameter
        'winbind request timeout ='
        """
        verrors = ValidationErrors()
        config = await self.middleware.call('activedirectory.config')
        if not config['enable']:
            await self.middleware.call('directoryservices.set_state', {'activedirectory': DSStatus['DISABLED'].name})
            return False

        """
        Initialize state to "JOINING" until after booted.
        """
        if not await self.middleware.call('system.ready'):
            await self.middleware.call('directoryservices.set_state', {'activedirectory': DSStatus['JOINING'].name})
            return True

        await self.middleware.call('activedirectory.common_validate', config, config, verrors)

        try:
            verrors.check()
        except ValidationErrors as ve:
            await self.middleware.call(
                'datastore.update', self._config.datastore, config['id'],
                {"enable": False}, {'prefix': 'ad_'}
            )
            raise CallError('Automatically disabling ActiveDirectory service due to invalid configuration',
                            errno.EINVAL, ', '.join([err[1] for err in ve]))

        """
        Verify winbindd netlogon connection.
        """
        await self.middleware.call('activedirectory.winbind_status')
        await self.middleware.call('directoryservices.set_state', {'activedirectory': DSStatus['HEALTHY'].name})
        return True
