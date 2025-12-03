import time

from middlewared.api.current import ContainersMetricsEventSourceArgs, ContainersMetricsEventSourceEvent
from middlewared.event import EventSource
from middlewared.plugins.reporting.realtime_reporting.cgroup import get_cgroup_stats
from middlewared.service import Service


class ContainersMetricsEventSource(EventSource):
    args = ContainersMetricsEventSourceArgs
    event = ContainersMetricsEventSourceEvent
    roles = ['CONTAINER_READ']

    def run_sync(self):
        interval = self.arg['interval']
        while not self._cancel_sync.is_set():
            netdata_metrics = None
            containers_mapping = {}
            retries = 2
            while retries > 0:
                try:
                    netdata_metrics = self.middleware.call_sync('netdata.get_all_metrics')
                    containers_mapping = {
                        f'lxc/{inst["uuid"].replace("-", "")}': inst['id'] for inst in self.middleware.call_sync(
                            'container.query', [], {'select': ['uuid', 'id'], 'force_sql_filters': True}
                        )
                    }
                except Exception:
                    retries -= 1
                    if retries <= 0:
                        raise

                    time.sleep(0.5)
                else:
                    break

            if netdata_metrics and containers_mapping:
                containers_status = get_cgroup_stats(netdata_metrics, containers_mapping.keys())
                self.send_event('ADDED', fields={
                    containers_mapping[cgroup_name]: stats for cgroup_name, stats in containers_status.items()
                })

            time.sleep(interval)


class ContainersService(Service):

    class Config:
        cli_namespace = 'service.container'
        event_sources = {
            'container.metrics': ContainersMetricsEventSource,
        }
