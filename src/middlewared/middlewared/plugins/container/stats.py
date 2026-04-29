import time

from middlewared.api.current import ContainersMetricsEventSourceArgs, ContainersMetricsEventSourceEvent, QueryOptions
from middlewared.event import TypedEventSource
from middlewared.plugins.reporting.realtime_reporting.cgroup import get_cgroup_stats
from middlewared.service import Service


class ContainersMetricsEventSource(TypedEventSource[ContainersMetricsEventSourceArgs]):
    args = ContainersMetricsEventSourceArgs
    event = ContainersMetricsEventSourceEvent
    roles = ["CONTAINER_READ"]

    def run_sync(self) -> None:
        interval = self.typed_arg.interval
        while not self._cancel_sync.is_set():
            netdata_metrics = None
            containers_mapping = {}
            retries = 2
            while retries > 0:
                try:
                    netdata_metrics = self.middleware.call_sync("netdata.get_all_metrics")
                    containers_mapping = {
                        f'lxc/{inst.uuid.replace("-", "")}': inst.id for inst in self.middleware.call_sync2(
                            self.middleware.services.container.query, [], QueryOptions(force_sql_filters=True)
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
                containers_status = get_cgroup_stats(netdata_metrics, list(containers_mapping))
                self.send_event("ADDED", fields={
                    containers_mapping[cgroup_name]: stats for cgroup_name, stats in containers_status.items()
                })

            time.sleep(interval)


class ContainersService(Service):

    class Config:
        cli_namespace = "service.container"
        event_sources = {
            "container.metrics": ContainersMetricsEventSource,
        }
