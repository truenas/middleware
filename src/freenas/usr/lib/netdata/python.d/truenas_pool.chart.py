from bases.FrameworkServices.SimpleService import SimpleService

from middlewared.utils.metrics.pool_stats import get_pool_dataset_stats


class Service(SimpleService):
    def __init__(self, configuration=None, name=None):
        SimpleService.__init__(self, configuration=configuration, name=name)
        self.update_every = 300

    def check(self):
        self.add_pool_stats_to_charts()
        return True

    def get_data(self):
        data = {}
        for pool_guid, info in get_pool_dataset_stats().items():
            self.add_chart_dimension(pool_guid)
            for i, value in info.items():
                data[f'{pool_guid}.{i}'] = value
            data[f'{pool_guid}.total'] = info['used'] + info['available']
        return data

    def add_pool_stats_to_charts(self):
        data = get_pool_dataset_stats()
        self.charts.add_chart([
            'usage', 'usage', 'usage', 'bytes',
            'pool.usage',
            'pool.usage',
            'line',
        ])

        for pool_guid in data.keys():
            self.add_chart_dimension(pool_guid)

    def add_chart_dimension(self, pool_guid):
        for identifier in ('available', 'used', 'total'):
            if f'{pool_guid}.{identifier}' in self.charts['usage']:
                continue
            self.charts['usage'].add_dimension([f'{pool_guid}.{identifier}', identifier, 'absolute'])
