from bases.FrameworkServices.SimpleService import SimpleService

from middlewared.utils.metrics.pool_stats import get_pool_dataset_stats


class Service(SimpleService):
    def __init__(self, configuration=None, name=None):
        SimpleService.__init__(self, configuration=configuration, name=name)
        self.old_stats = {}

    def check(self):
        self.add_pool_stats_to_charts()
        return True

    def get_data(self):
        data = {}
        for pool_name, info in get_pool_dataset_stats().items():
            for i, value in info.items():
                data[f'{pool_name}.{i}'] = value
        return data

    def add_pool_stats_to_charts(self):
        data = get_pool_
        dataset_stats()
        self.charts.add_chart([
            'usage', 'usage', 'usage', 'bytes',
            'pool.usage',
            'pool.usage',
            'line',
        ])

        for pool_name in data.keys():
            self.charts['usage'].add_dimension([f'{pool_name}.available', f'available', 'absolute'])
            self.charts['usage'].add_dimension([f'{pool_name}.used', f'used', 'absolute'])
