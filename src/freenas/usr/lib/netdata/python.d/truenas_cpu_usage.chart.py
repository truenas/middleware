from bases.FrameworkServices.SimpleService import SimpleService

from middlewared.utils.metrics.cpu_usage import get_cpu_usage


class Service(SimpleService):
    def __init__(self, configuration=None, name=None):
        SimpleService.__init__(self, configuration=configuration, name=name)

    def check(self):
        self.add_cpu_usage_to_charts()
        return True

    def get_data(self):
        return get_cpu_usage()

    def add_cpu_usage_to_charts(self):
        for cpu_name in get_cpu_usage().keys():
            self.charts.add_chart([
                cpu_name, cpu_name, cpu_name, 'CPU USAGE%',
                'cpu.usage',
                'Cpu usage',
                'line',
            ])

            self.charts[cpu_name].add_dimension([cpu_name, 'usage', 'absolute'])
