from bases.FrameworkServices.SimpleService import SimpleService

from middlewared.utils.metrics.cpu_usage import get_cpu_usage


class Service(SimpleService):
    def __init__(self, configuration=None, name=None):
        SimpleService.__init__(self, configuration=configuration, name=name)
        self.old_stats = {}

    def check(self):
        self.add_cpu_usage_to_charts()
        return True

    def get_data(self):
        data, self.old_stats = get_cpu_usage(self.old_stats)
        return data

    def add_cpu_usage_to_charts(self):
        data, self.old_stats = get_cpu_usage()
        self.charts.add_chart([
            'cpu', 'cpu', 'cpu', 'CPU USAGE%',
            'cpu.usage',
            'Cpu usage',
            'line',
        ])

        for cpu_name in filter(lambda s: s.startswith('cpu'), data.keys()):
            self.charts['cpu'].add_dimension([f'{cpu_name}', f'{cpu_name}', 'absolute'])
