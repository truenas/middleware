from subprocess import DEVNULL, run

from middlewared.api import api_method
from middlewared.api.current import (
    IpmiChassisIdentifyArgs,
    IpmiChassisIdentifyResult,
    IpmiChassisInfoArgs,
    IpmiChassisInfoResult,
)
from middlewared.service import Service, ValidationError, private


class IpmiChassisService(Service):

    class Config:
        namespace = 'ipmi.chassis'
        cli_namespace = 'service.ipmi.chassis'

    @private
    def info_impl(self):
        """Implementation method to get IPMI chassis info from local system."""
        rv = {}
        if not self.middleware.call_sync('ipmi.is_loaded'):
            return rv

        out = run(['ipmi-chassis', '--get-chassis-status'], capture_output=True)
        for line in filter(lambda x: x, out.stdout.decode().split('\n')):
            ele, status = line.split(':', 1)
            rv[ele.strip().replace(' ', '_').lower()] = status.strip()

        return rv

    @api_method(
        IpmiChassisInfoArgs,
        IpmiChassisInfoResult,
        roles=['IPMI_READ'],
    )
    def info(self, data):
        """
        Return IPMI chassis info.

        On an HA system, set ``query-remote`` to ``true`` to return the chassis info from the
        remote controller instead of the local one.
        """
        query_remote = data.get('query-remote', False)
        result = {}
        if not query_remote:
            result = self.info_impl()
        elif self.middleware.call_sync('failover.licensed'):
            try:
                # Call public method 'info' on remote without parameters
                # This executes locally on the remote node (query_remote defaults to False)
                result = self.middleware.call_sync(
                    'failover.call_remote', 'ipmi.chassis.info'
                )
            except Exception:
                result = {}

        return result

    @private
    def identify_impl(self, verb):
        """Implementation method to set IPMI chassis identify state on local system."""
        if self.middleware.call_sync('ipmi.is_loaded'):
            verb = 'force' if verb == 'ON' else '0'
            run(['ipmi-chassis', f'--chassis-identify={verb}'], stdout=DEVNULL, stderr=DEVNULL)

    @api_method(
        IpmiChassisIdentifyArgs,
        IpmiChassisIdentifyResult,
        roles=['IPMI_WRITE'],
    )
    def identify(self, data):
        """
        Toggle the chassis identify light on or off.

        On an HA system, set ``apply_remote`` to ``true`` to apply the change to the remote
        controller instead of the local one.
        """
        verb = data.get('verb', 'ON')
        apply_remote = data.get('apply_remote', False)

        if not apply_remote:
            self.identify_impl(verb)
        elif self.middleware.call_sync('failover.licensed'):
            try:
                # Call public method 'identify' on remote without parameters
                # This executes locally on the remote node (apply_remote defaults to False)
                self.middleware.call_sync(
                    'failover.call_remote', 'ipmi.chassis.identify', [{'verb': verb}]
                )
            except Exception as e:
                raise ValidationError(
                    'ipmi.chassis.identify',
                    f'Failed to apply chassis identify on remote controller: {e}'
                )
