from subprocess import run, DEVNULL

from middlewared.api import api_method
from middlewared.api.current import (
    IpmiChassisIdentifyArgs,
    IpmiChassisIdentifyResult,
    IpmiChassisInfoArgs,
    IpmiChassisInfoResult,
)
from middlewared.service import Service


class IpmiChassisService(Service):

    class Config:
        namespace = 'ipmi.chassis'
        cli_namespace = 'service.ipmi.chassis'

    @api_method(
        IpmiChassisInfoArgs,
        IpmiChassisInfoResult,
        roles=['IPMI_READ'],
    )
    def info(self):
        """Return IPMI chassis info."""
        rv = {}
        if not self.middleware.call_sync('ipmi.is_loaded'):
            return rv

        out = run(['ipmi-chassis', '--get-chassis-status'], capture_output=True)
        for line in filter(lambda x: x, out.stdout.decode().split('\n')):
            ele, status = line.split(':', 1)
            rv[ele.strip().replace(' ', '_').lower()] = status.strip()

        return rv

    @api_method(
        IpmiChassisIdentifyArgs,
        IpmiChassisIdentifyResult,
        roles=['IPMI_WRITE'],
    )
    def identify(self, verb):
        """
        Toggle the chassis identify light.

        `verb`: str if 'ON' turn identify light on. if 'OFF' turn identify light off.
        """
        verb = 'force' if verb == 'ON' else '0'
        run(['ipmi-chassis', f'--chassis-identify={verb}'], stdout=DEVNULL, stderr=DEVNULL)
