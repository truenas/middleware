from copy import deepcopy

from bases.FrameworkServices.SimpleService import SimpleService

from middlewared.utils.cpu import get_cpu_temperatures


ORDER = [
    'temperatures',
]

# This is a prototype of chart definition which is used to dynamically create self.definitions
CHARTS = {
    'temperatures': {
        'options': [None, 'Temperature', 'Celsius', 'temperature', 'sensors.temperature', 'line'],
        'lines': []
    }
}


class Service(SimpleService):
    def __init__(self, configuration=None, name=None):
        SimpleService.__init__(self, configuration=configuration, name=name)
        self.order = deepcopy(ORDER)
        self.definitions = deepcopy(CHARTS)

    def get_data(self):
        return get_cpu_temperatures()

    def check(self):
        data = self.get_data()
        for i in data:
            self.definitions['temperatures']['lines'].append([str(i)])

        return bool(data)
