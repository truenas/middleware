import time

from middlewared.event import EventSource
from middlewared.schema import Dict, Float, Int
from middlewared.service import Service
from middlewared.utils.disks import get_disk_names, get_disks_with_identifiers
from middlewared.validators import Range

from .realtime_reporting import get_arc_stats, get_cpu_stats, get_disk_stats, get_interface_stats, get_memory_info


class ReportingRealtimeService(Service):

    class Config:
        namespace = 'reporting.realtime'
        private = True

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

        if failed_to_connect := not bool(netdata_metrics):
            data = {'failed_to_connect': failed_to_connect}
        else:
            disks = get_disk_names()
            if len(disks) != len(disk_mapping):
                disk_mapping = get_disks_with_identifiers()

            data = {
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
                'failed_to_connect': False,
            }

        return data


class RealtimeEventSource(EventSource):

    """
    Retrieve real time statistics for CPU, network,
    virtual memory and zfs arc.
    """
    ACCEPTS = Dict(
        Int('interval', default=2, validators=[Range(min_=2)]),
    )
    RETURNS = Dict(
        Dict('cpu', additional_attrs=True),
        Dict(
            'disks',
            Float('busy'),
            Float('read_bytes'),
            Float('write_bytes'),
            Float('read_ops'),
            Float('write_ops'),
        ),
        Dict('interfaces', additional_attrs=True),
        Dict(
            'memory',
            Int('arc_size'),
            Int('arc_free_memory'),
            Int('arc_available_memory'),
            Int('physical_memory_total'),
            Int('physical_memory_available'),
        ),
        Dict(
            'zfs',
            Int('demand_accesses_per_second'),
            Int('demand_data_accesses_per_second'),
            Int('demand_metadata_accesses_per_second'),
            Int('demand_data_hits_per_second'),
            Int('demand_data_io_hits_per_second'),
            Int('demand_data_misses_per_second'),
            Int('demand_data_hit_percentage'),
            Int('demand_data_io_hit_percentage'),
            Int('demand_data_miss_percentage'),
            Int('demand_metadata_hits_per_second'),
            Int('demand_metadata_io_hits_per_second'),
            Int('demand_metadata_misses_per_second'),
            Int('demand_metadata_hit_percentage'),
            Int('demand_metadata_io_hit_percentage'),
            Int('demand_metadata_miss_percentage'),
            Int('l2arc_hits_per_second'),
            Int('l2arc_misses_per_second'),
            Int('total_l2arc_accesses_per_second'),
            Int('l2arc_access_hit_percentage'),
            Int('l2arc_miss_percentage'),
            Int('bytes_read_per_second_from_the_l2arc'),
            Int('bytes_written_per_second_to_the_l2arc'),
        )
    )

    def run_sync(self):
        interval = self.arg['interval']
        disk_mapping = get_disks_with_identifiers()

        while not self._cancel_sync.is_set():
            self.send_event('ADDED', fields=self.middleware.call_sync('reporting.realtime.stats', disk_mapping))
            time.sleep(interval)


def setup(middleware):
    middleware.register_event_source('reporting.realtime', RealtimeEventSource, roles=['REPORTING_READ'])
