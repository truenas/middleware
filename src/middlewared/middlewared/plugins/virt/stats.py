import time

from middlewared.api.current import VirtInstancesMetricsEventSourceArgs, VirtInstancesMetricsEventSourceEvent
from middlewared.event import EventSource
from middlewared.plugins.reporting.realtime_reporting.cgroup import get_cgroup_stats
from middlewared.service import Service


class VirtInstancesMetricsEventSource(EventSource):
    args = VirtInstancesMetricsEventSourceArgs
    event = VirtInstancesMetricsEventSourceEvent
    roles = ['VIRT_INSTANCE_READ']

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


class VirtInstanceService(Service):

    class Config:
        cli_namespace = 'virt.instance'
        event_sources = {
            'virt.instance.metrics': VirtInstancesMetricsEventSource,
        }
