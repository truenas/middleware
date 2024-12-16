from middlewared.utils.memory import get_memory_info

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
        return {'total': get_memory_info()['total']}

    def check(self):
        return True
