from bases.FrameworkServices.SimpleService import SimpleService

from middlewared.plugins.reporting.realtime_reporting import get_gpu_stats
from middlewared.utils.metrics.gpu_usage import get_gpu_usage


class Service(SimpleService):
    def __init__(self, configuration=None, name=None):
        SimpleService.__init__(self, configuration=configuration, name=name)
        self.old_stats = {}

    def check(self):
        self.add_gpu_usage_to_charts()
        return True

    def get_data(self):
        data, self.old_stats = get_gpu_stats(self.old_stats)
        return data

    def add_gpu_usage_to_charts(self):
        data, self.old_stats = get_gpu_usage()
        self.charts.add_chart([
            'gpu', 'gpu', 'gpu', 'GPU USAGE%',
            'gpu.usage',
            'Gpu usage',
            'line',
        ])

        for gpu_name in filter(lambda s: s.startswith('gpu'), data.keys()):
            self.charts['gpu'].add_dimension([f'{gpu_name}', f'{gpu_name}', 'absolute'])
