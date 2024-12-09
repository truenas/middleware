from dataclasses import asdict

from middlewared.utils.metrics.meminfo import get_memory_info

from bases.FrameworkServices.SimpleService import SimpleService


CHARTS = {
    'total': {
        'options': [None, 'total', 'Bytes', 'total', 'Total memory', 'line'],
        'lines': [
            ['total', 'total', 'absolute'],
        ]
    },
}


class Service(SimpleService):
    def __init__(self, configuration=None, name=None):
        SimpleService.__init__(self, configuration=configuration, name=name)
        self.order = [chart_name for chart_name in CHARTS.keys()]
        self.definitions = CHARTS

    def get_data(self):
        data = {}
        for key, value in asdict(get_memory_info()).items():
            data[key] = value
        return data

    def check(self):
        return True
