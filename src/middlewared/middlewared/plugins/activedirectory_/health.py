import errno
import subprocess
import wbclient

from middlewared.plugins.smb import SMBCmd
from middlewared.plugins.activedirectory_.dns import SRV
from middlewared.schema import accepts
from middlewared.service import private, Service, ValidationErrors
from middlewared.service_exception import CallError
from middlewared.plugins.directoryservices import DSStatus
from middlewared.plugins.idmap_.utils import WBClient, WBCErr


class ActiveDirectoryService(Service):

    class Config:
        service = "activedirectory"

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
                ad['timeout'],
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
                for dc_to_check in res:
                    thehost = dc_to_check['host']
                    if thehost.casefold() != our_dc.casefold():
                        found_dc = thehost
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

    @accepts()
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
        except ValidationErrors:
            await self.middleware.call('activedirectory.direct_update', {"enable": False})
            raise CallError('Automatically disabling ActiveDirectory service due to invalid configuration.',
                            errno.EINVAL)

        """
        Verify winbindd netlogon connection.
        """
        await self.middleware.call('activedirectory.winbind_status')

        if (await self.middleware.call('smb.get_smb_ha_mode')) == 'CLUSTERED':
            state_method = 'clustercache.get'
        else:
            state_method = 'cache.get'

        try:
            cached_state = await self.middleware.call(state_method, 'DS_STATE')

            if cached_state['activedirectory'] != 'HEALTHY':
                await self.middleware.call('directoryservices.set_state', {'activedirectory': DSStatus['HEALTHY'].name})
        except KeyError:
            await self.middleware.call('directoryservices.set_state', {'activedirectory': DSStatus['HEALTHY'].name})

        return True
