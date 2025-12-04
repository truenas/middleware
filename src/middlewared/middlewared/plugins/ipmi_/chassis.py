from subprocess import run, DEVNULL

from middlewared.api import api_method
from middlewared.api.current import (
    IpmiChassisIdentifyArgs,
    IpmiChassisIdentifyResult,
    IpmiChassisInfoArgs,
    IpmiChassisInfoResult,
)
from middlewared.service import private, Service, ValidationError


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

        `query-remote`: [optional] if True on HA system, then return info from remote controller.
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

    @api_method(
        IpmiChassisIdentifyArgs,
        IpmiChassisIdentifyResult,
        roles=['IPMI_WRITE'],
    )
    def identify(self, data):
        """
        Toggle the chassis identify light.

        `verb`: str if 'ON' turn identify light on. if 'OFF' turn identify light off.
        `apply_remote`: bool if True on HA systems, apply to remote controller.
        """
        verb = data.get('verb', 'ON')
        apply_remote = data.get('apply_remote', False)

        if apply_remote and self.middleware.call_sync('failover.licensed'):
            try:
                # Call remote with dict parameter (no apply_remote to avoid loop)
                # Wrap in list to pass as positional parameter
                return self.middleware.call_sync(
                    'failover.call_remote', 'ipmi.chassis.identify', [{'verb': verb}]
                )
            except Exception as e:
                raise ValidationError(
                    'ipmi.chassis.identify',
                    f'Failed to apply chassis identify on remote controller: {e}'
                )

        verb = 'force' if verb == 'ON' else '0'
        run(['ipmi-chassis', f'--chassis-identify={verb}'], stdout=DEVNULL, stderr=DEVNULL)
