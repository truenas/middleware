import errno
import subprocess

from middlewared.plugins.smb import SMBCmd, WBCErr
from middlewared.plugins.activedirectory_.dns import SRV
from middlewared.schema import accepts
from middlewared.service import private, Service, ValidationErrors
from middlewared.service_exception import CallError
from middlewared.utils import run
from middlewared.plugins.directoryservices import DSStatus


class ActiveDirectoryService(Service):

    class Config:
        service = "activedirectory"

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
        if data is None:
            data = self.middleware.call_sync("activedirectory.config")
        if dc is None:
            res = self.middleware.call_sync('activedirectory.get_n_working_srvers',
                data['domainname'], SRV.DOMAINCONTROLLER.name, data['site'],
                2, data['timeout'], data['verbose_logging']
            )
            if len(res) != 2:
                self.logger.warning("Less than two Domain Controllers are in our "
                                    "Active Directory Site. This may result in production "
                                    "outage if the currently connected DC is unreachable.")
                return False

            """
            In some pathologically bad cases attempts to get the DC that winbind is currently
            communicating with can time out. For this particular health check, the winbind
            error should not be considered fatal.
            """
            wb_dcinfo = subprocess.run([SMBCmd.WBINFO.value, "--dc-info", data["domainname"]],
                                       capture_output=True, check=False)
            if wb_dcinfo.returncode == 0:
                # output "FQDN (ip address)"
                our_dc = wb_dcinfo.stdout.decode().split()[0]
                for dc_to_check in res:
                    thehost = dc_to_check['host']
                    if thehost.casefold() != our_dc.casefold():
                        dc = thehost
            else:
                self.logger.warning("Failed to get DC info from winbindd: %s", wb_dcinfo.stderr.decode())
                dc = res[0]['host']

        return True

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

        await self.middleware.call('activedirectory.common_validate', config, config, verrors)

        try:
            verrors.check()
        except Exception:
            await self.middleware.call('activedirectory.direct_update', {"enable": False})
            raise CallError('Automatically disabling ActiveDirectory service due to invalid configuration.',
                            errno.EINVAL)

        """
        Initialize state to "JOINING" until after booted.
        """
        if not await self.middleware.call('system.ready'):
            await self.middleware.call('directoryservices.set_state', {'activedirectory': DSStatus['JOINING'].name})
            return True

        """
        Verify winbindd netlogon connection.
        """
        netlogon_ping = await run([SMBCmd.WBINFO.value, '-P'], check=False)
        if netlogon_ping.returncode != 0:
            wberr = netlogon_ping.stderr.decode().strip('\n')
            err = errno.EFAULT
            for wb in WBCErr:
                if wb.err() in wberr:
                    wberr = wberr.replace(wb.err(), wb.value[0])
                    err = wb.value[1] if wb.value[1] else errno.EFAULT
                    break

            raise CallError(wberr, err)

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
