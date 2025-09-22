import time

from middlewared.api.current import ReportingRealtimeEventSourceArgs, ReportingRealtimeEventSourceEvent
from middlewared.event import EventSource
from middlewared.service import private, Service
from middlewared.utils.disks_.disk_class import iterate_disks

from .realtime_reporting import (
    get_arc_stats, get_cpu_stats, get_disk_stats, get_interface_stats, get_memory_info, get_pool_stats,
)


def get_disks_with_identifiers() -> dict[str, str]:
    return {i.name: i.identifier for i in iterate_disks()}


class RealtimeEventSource(EventSource):
    """
    Retrieve real time statistics for CPU, network,
    virtual memory and zfs arc.
    """

    args = ReportingRealtimeEventSourceArgs
    event = ReportingRealtimeEventSourceEvent
    roles = ['REPORTING_READ']

    def run_sync(self):
        interval = self.arg['interval']
        disk_mapping = get_disks_with_identifiers()

        while not self._cancel_sync.is_set():
            fields = self.middleware.call_sync('reporting.realtime.stats', disk_mapping)
            if fields:
                self.send_event('ADDED', fields=fields)
            time.sleep(interval)


class ReportingRealtimeService(Service):

    class Config:
        namespace = 'reporting.realtime'
        cli_private = True
        event_sources = {
            'reporting.realtime': RealtimeEventSource,
        }

    @private
    def stats(self, disk_mapping=None):
        disk_mapping = disk_mapping or get_disks_with_identifiers()
        # this gathers the most recent metric recorded via netdata (for all charts)
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

        data = dict()
        if netdata_metrics:
            disks = list(iterate_disks())
            if len(disks) != len(disk_mapping):
                disk_mapping = get_disks_with_identifiers()

            data.update({
                'zfs': get_arc_stats(netdata_metrics),  # ZFS ARC Size
                'memory': get_memory_info(netdata_metrics),
                'cpu': get_cpu_stats(netdata_metrics),
                'disks': get_disk_stats(netdata_metrics, disks, disk_mapping),
                'interfaces': get_interface_stats(
                    netdata_metrics, [
                        iface['name'] for iface in self.middleware.call_sync(
                            'interface.query', [], {'extra': {'retrieve_names_only': True}}
                        )
                    ]
                ),
                'pools': get_pool_stats(netdata_metrics),
            })

        return data
