import time

from bases.collection import safe_print
from bases.FrameworkServices.SimpleService import ND_INTERNAL_MONITORING_DISABLED, RUNTIME_CHART_UPDATE, SimpleService
from third_party.monotonic import monotonic

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
            self.charts['usage'].add_dimension([f'{pool_guid}.available', 'available', 'absolute'])
            self.charts['usage'].add_dimension([f'{pool_guid}.used', 'used', 'absolute'])
            self.charts['usage'].add_dimension([f'{pool_guid}.total', 'total', 'absolute'])

    # We would like to override netdata's run method to avoid having a 10 minute delay before we actually
    # get stats, now with these changes we will have a 5 minute delay before we get our first data point
    # for this plugin
    def run(self):
        """
        Runs job in thread. Handles retries.
        Exits when job failed or timed out.
        :return: None
        """
        job = self._runtime_counters
        self.debug('started, update frequency: {freq}'.format(freq=job.update_every))

        job.start_mono = monotonic()
        job.start_real = time.time()

        while True:
            since = 0
            if job.prev_update:
                since = int((job.start_real - job.prev_update) * 1e6)

            try:
                updated = self.update(interval=since)
            except Exception as error:
                self.error('update() unhandled exception: {error}'.format(error=error))
                updated = False

            job.runs += 1

            if not updated:
                job.handle_retries()
            else:
                job.elapsed = int((monotonic() - job.start_mono) * 1e3)
                job.prev_update = job.start_real
                job.retries, job.penalty = 0, 0
                if not ND_INTERNAL_MONITORING_DISABLED:
                    safe_print(RUNTIME_CHART_UPDATE.format(job_name=self.name,
                                                           since_last=since,
                                                           elapsed=job.elapsed))
            self.debug('update => [{status}] (elapsed time: {elapsed}, failed retries in a row: {retries})'.format(
                status='OK' if updated else 'FAILED',
                elapsed=job.elapsed if updated else '-',
                retries=job.retries))

            job.sleep_until_next()
