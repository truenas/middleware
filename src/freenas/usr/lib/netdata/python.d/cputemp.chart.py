from bases.FrameworkServices.SimpleService import SimpleService
from copy import deepcopy

from middlewared.utils.cpu import cpu_info, cpu_temperatures


CHARTS = {
    'temperatures': {
        'options': ['cpu_temp', 'CPU Temperatures', 'Celsius', 'temperatures', 'cpu.temperatures', 'line'],
        'lines': []
    },
}
ORDER = [
    'temperatures',
]


class Service(SimpleService):
    def __init__(self, configuration=None, name=None):
        SimpleService.__init__(self, configuration=configuration, name=name)
        self.order = ORDER
        self.definitions = deepcopy(CHARTS)
        self.update_every = 1

    def check(self):
        for i in range(cpu_info()['core_count']):
            self.definitions['temperatures']['lines'].append([str(i)])
        return True

    def _get_data(self):
        return cpu_temperatures() or {str(i): None for i in range(cpu_info()['core_count'])}
