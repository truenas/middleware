from bases.FrameworkServices.SimpleService import SimpleService
from copy import deepcopy

from middlewared.utils.disks import get_disks_for_temperature_reading, get_disks_temperatures


CHARTS = {
    'temperatures': {
        'options': ['disks_temp', 'Disks Temperatures', 'Celsius', 'temperatures', 'disktemp.temperatures', 'line'],
        'lines': [],
    }
}
ORDER = [
    'temperatures',
]


class Service(SimpleService):
    def __init__(self, configuration=None, name=None):
        SimpleService.__init__(self, configuration=configuration, name=name)
        self.order = ORDER
        self.definitions = deepcopy(CHARTS)
        self._keep_alive = False

    def check(self):
        for d in get_disks_for_temperature_reading():
            self.definitions['temperatures']['lines'].append([d.id])
        return True

    def _get_data(self):
        for non_registered_disks in filter(
            lambda disk: disk.id not in self.charts['temperatures'],
            get_disks_for_temperature_reading()
        ):
            self.charts['temperatures'].add_dimension([non_registered_disks.id])
        return get_disks_temperatures() or {disk.id: None for disk in get_disks_for_temperature_reading()}
