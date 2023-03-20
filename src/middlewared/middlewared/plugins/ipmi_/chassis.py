from subprocess import run, DEVNULL, PIPE

from middlewared.service import Service, filterable, filterable_returns
from middlewared.utils import filter_list
from middlewared.schema import Str, Dict, accepts, returns


class IpmiChassisService(Service):

    class Config:
        namespace = 'ipmi.chassis'
        cli_namespace = 'service.ipmi.chassis'

    @filterable
    @filterable_returns(Dict('chassis_info', additional_attrs=True))
    def query(self, filters, options):
        rv = {}
        out = run(['ipmi-chassis', '--get-chassis-status'], stdout=PIPE, stderr=PIPE).stdout.decode().split('\n')
        for line in filter(lambda x: x, out):
            ele, status = line.split(':', 1)
            rv[ele.strip()] = status.strip()

        return filter_list(rv, filters, options)

    @accepts(Str('verb', default='ON', enum=['ON', 'OFF']))
    @returns()
    def identify(self, verb):
        """
        Toggle the chassis identify light.

        `verb`: str if 'ON' turn identify light on. if 'OFF' turn identify light off.
        """
        verb = 'force' if verb == 'ON' else '0'
        run(['ipmi-chassis', f'--chassis-identify={verb}'], stdout=DEVNULL, stderr=DEVNULL)
