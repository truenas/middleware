import time

from middlewared.event import EventSource
from middlewared.schema import Dict, Int
from middlewared.plugins.reporting.realtime_reporting.cgroup import get_cgroup_stats
from middlewared.validators import Range


class VirtInstancesMetricsEventSource(EventSource):

    ACCEPTS = Dict(
        Int('interval', default=2, validators=[Range(min_=2)]),
    )

    def run_sync(self):

        interval = self.arg['interval']
        while not self._cancel_sync.is_set():
            netdata_metrics = None
            retries = 2
            while retries > 0:
                try:
                    netdata_metrics = self.middleware.call_sync('netdata.get_all_metrics')
                except Exception:
                    retries -= 1
                    if retries <= 0:
                        raise

                    time.sleep(0.5)
                else:
                    break

            if netdata_metrics:
                self.send_event('ADDED', fields=get_cgroup_stats(
                    netdata_metrics, self.middleware.call_sync('virt.instance.get_instance_names')
                ))

            time.sleep(interval)


async def setup(middleware):
    middleware.register_event_source(
        'virt.instance.metrics', VirtInstancesMetricsEventSource, roles=['VIRT_INSTANCE_READ']
    )
