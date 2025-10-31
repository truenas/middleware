from random import uniform
from subprocess import run
from time import sleep

from middlewared.service import Service
from middlewared.utils.filter_list import filter_list


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
        private = True
        cli_namespace = 'service.ipmi.sensors'

    def query_impl(self):
        rv, reread = [], None
        if not self.middleware.call_sync('ipmi.is_loaded'):
            return rv, reread

        mseries = self.middleware.call_sync('failover.hardware') == 'ECHOWARP'
        for line in filter(lambda x: x, get_sensors_data()):
            if (values := line.split(',')) and len(values) == 13:
                sensor = {
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
                }
                if sensor['type'] == 'Power Supply' and mseries and 'no presence detected' in sensor['event']:
                    # PMBus (which controls the PSU's status) can not be probed at the same time because
                    # it's not a shared bus. HA systems show false positive "no presence detected" more
                    # often because both controllers are randomly probing the status of the PSU's at the
                    # same time because this method is called in an alert. The alert, by default, gets
                    # called on both controllers.
                    reread = f'"{sensor["name"]}" reporting "no presence detected"'

                rv.append(sensor)

        return rv, reread

    def query(self, filters: list | None = None, options: dict | None = None):
        if filters is None:
            filters = list()
        if options is None:
            options = dict()

        sensors, reread = self.query_impl()
        if reread is not None:
            max_retries = 3
            while max_retries != 0:
                self.logger.info('%s re-reading', reread)
                sleep(round(uniform(0.4, 1.2), 2))
                sensors, reread = self.query_impl()
                if reread is None:
                    # re-read the sensors list and PSU status came back
                    # healthy so exit early
                    break
                else:
                    max_retries -= 1

        return filter_list(sensors, filters, options)
