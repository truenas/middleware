from subprocess import run

from middlewared.service import Service, filterable, filterable_returns
from middlewared.utils import filter_list
from middlewared.schema import List, Dict


def get_sensors_data():
    cmd = [
        'ipmi-sensors',
        '--comma-separated',
        '--no-header-output',
        '--non-abbreviated-units',
        '--output-sensor-state',
        '--output-sensor-thresholds',
    ]
    rv = []
    cp = run(cmd, capture_output=True)
    if cp.returncode == 0 and cp.stdout:
        rv = cp.stdout.decode().split('\n')

    return rv


class IpmiSensorsService(Service):

    class Config:
        namespace = 'ipmi.sensors'
        cli_namespace = 'service.ipmi.sensors'

    @filterable
    @filterable_returns(List('sensors', items=[Dict('sensor', additional_attrs=True)]))
    def query(self, filters, options):
        rv = []
        if not self.middleware.call_sync('system.dmidecode_info')['has-ipmi']:
            return rv

        for line in filter(lambda x: x, get_sensors_data()):
            if (values := line.split(',')) and len(values) == 13:
                rv.append({
                    'id': values[0],
                    'name': values[1],
                    'type': values[2],
                    'state': values[3],
                    'reading': values[4],
                    'units': values[5],
                    'lower-non-recoverable': values[6],
                    'lower-critical': values[7],
                    'lower-non-critical': values[8],
                    'upper-non-critical': values[9],
                    'upper-critical': values[10],
                    'upper-non-recoverable': values[11],
                    'event': [i.replace("'", '').strip().lower() for i in values[12].split("' '")]
                })

        return filter_list(rv, filters, options)
