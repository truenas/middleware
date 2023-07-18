import psutil
import time

from middlewared.event import EventSource
from middlewared.schema import Dict, Float, Int
from middlewared.validators import Range

from .realtime_reporting import get_arc_stats, get_cpu_stats, get_disk_stats, get_interface_stats, get_memory_info


class RealtimeEventSource(EventSource):

    """
    Retrieve real time statistics for CPU, network,
    virtual memory and zfs arc.
    """
    ACCEPTS = Dict(
        Int('interval', default=2, validators=[Range(min=2)]),
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
            Dict(
                'classes',
                Int('apps'),
                Int('arc'),
                Int('buffers'),
                Int('cache'),
                Int('page_tables'),
                Int('slab_cache'),
                Int('swap_cache'),
                Int('unused'),
            ),
            Dict('extra', additional_attrs=True),
            Dict(
                'swap',
                Int('total'),
                Int('used'),
            )
        ),
        Dict('virtual_memory', additional_attrs=True),
        Dict(
            'zfs',
            Int('arc_max_size'),
            Int('arc_size'),
            Float('cache_hit_ratio'),
        ),
    )

    def run_sync(self):
        interval = self.arg['interval']
        cores = self.middleware.call_sync('system.info')['cores']

        while not self._cancel_sync.is_set():
            # this gathers the most recent metric recorded via netdata (for all charts)
            netdata_metrics = self.middleware.call_sync('netdata.get_all_metrics')

            data = {
                'zfs': get_arc_stats(netdata_metrics),  # ZFS ARC Size
                'memory': get_memory_info(netdata_metrics),
                'virtual_memory': psutil.virtual_memory()._asdict(),
                'cpu': get_cpu_stats(netdata_metrics, cores),
                'disks': get_disk_stats(netdata_metrics, list(self.middleware.call_sync('device.get_disks'))),
                'interfaces': get_interface_stats(
                    netdata_metrics, [i['name'] for i in self.middleware.call_sync('interface.query')]
                ),
            }

            # CPU temperature
            data['cpu']['temperature_celsius'] = self.middleware.call_sync('reporting.cpu_temperatures')
            data['cpu']['temperature'] = {k: 2732 + int(v * 10) for k, v in data['cpu']['temperature_celsius'].items()}

            self.send_event('ADDED', fields=data)
            time.sleep(interval)


def setup(middleware):
    middleware.register_event_source('reporting.realtime', RealtimeEventSource)
