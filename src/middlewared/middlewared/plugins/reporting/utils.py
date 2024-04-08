import collections
import contextlib
import typing

from .netdata.graph_base import GraphBase


K8S_PODS_COUNT = 20  # A default value has been assumed for now
# https://learn.netdata.cloud/docs/netdata-agent/configuration/optimizing-metrics-database/
# change-how-long-netdata-stores-metrics
TIER_0_POINT_SIZE = 1
TIER_1_POINT_SIZE = 4


def calculate_disk_space_for_netdata(
    metric_intervals: dict, days: int, bytes_per_point: int, tier_interval: int
) -> int:
    # Constants
    sec_per_day = 86400
    total_metrics = 0
    for collection_interval_seconds, metrics in metric_intervals.items():
        total_metrics += metrics / collection_interval_seconds

    required_disk_space_bytes = days * (sec_per_day / tier_interval) * bytes_per_point * total_metrics
    # Convert bytes to megabytes (1 MB = 1024 * 1024 bytes)
    required_disk_space_mb = required_disk_space_bytes / (1024 * 1024)

    return int(required_disk_space_mb)


def convert_unit(unit: str, page: int) -> int:
    return {
        'HOUR': 60 * 60,
        'DAY': 60 * 60 * 24,
        'WEEK': 60 * 60 * 24 * 7,
        'MONTH': 60 * 60 * 24 * 30,
        'YEAR': 60 * 60 * 24 * 365,
    }[unit] * page


async def fetch_data_from_graph_plugins(
    graph_plugins: typing.Dict[GraphBase, list], query_params: dict, aggregate: bool,
) -> collections.abc.AsyncIterable:
    for graph_plugin, identifiers in graph_plugins.items():
        await graph_plugin.build_context()
        with contextlib.suppress(Exception):
            yield await graph_plugin.export_multiple_identifiers(query_params, identifiers, aggregate=aggregate)


def get_metrics_approximation(disk_count: int, core_count: int, interface_count: int, pool_count: int) -> dict:
    data = {
        1: {
            'system.cpu': 10,
            'cpu.cpu': 10 * core_count,
            'cpu.cpu0_cpuidle': 4 * core_count,
            'cpu.cpufreq': core_count,
            'system.intr': 1,
            'system.ctxt': 1,
            'system.forks': 1,
            'system.processes': 2,
            'zfs_state_pool': pool_count * 6,
            'system.clock_sync_state': 1,
            'system.clock_status': 2,
            'system.clock_sync_offset': 1,

            # diskstats
            'system.io': 2,
            'disk': 2 * disk_count,
            'disk_ext': disk_count,
            'disk_ops': 2 * disk_count,
            'disk_ext_ops': 2 * disk_count,
            'disk_backlog': disk_count,
            'disk_busy': disk_count,
            'disk_util': disk_count,
            'disk_iotime': 2 * disk_count,
            'disk_ext_iotime': 2 * disk_count,
            'disk_svctm': 1 * disk_count,
            'disk_qops': 2 * disk_count,
            'disk_mops': 2 * disk_count,
            'disk_ext_mops': disk_count,
            'disk_avgsz': 2 * disk_count,
            'disk_ext_avgsz': disk_count,
            'disk_await': 2 * disk_count,
            'disk_ext_await': 2 * disk_count,

            # meminfo
            'system.ram': 4,
            'mem.available': 1,
            'system.swap': 2,
            'mem.committed': 1,
            'mem.writeback': 5,
            'mem.kernel': 5,
            'mem.slab': 2,
            'mem.transparent_hugepages': 2,

            # net
            'system.net': 2,
            'net': 2 * interface_count,
            'net_speed': interface_count,
            'net_duplex': 3 * interface_count,
            'net_operstate': 7 * interface_count,
            'net_mtu': interface_count,
            'net_packets': 3 * interface_count,
            'net_drops': 2 * interface_count,
            'net_carrier': 2 * interface_count,

            # uptime
            'system.uptime': 1,

            # loadavg
            'system.load': 3,
            'system.active_processes': 1,

            # zfs arcstats
            'zfs.arc_size': 4,
            'zfs.reads': 5,
            'zfs.hits': 2,
            'zfs.hits_rate': 2,
            'zfs.dhits': 2,
            'zfs.dhits_rate': 2,
            'zfs.phits': 2,
            'zfs.phits_rate': 2,
            'zfs.mhits': 2,
            'zfs.mhits_rate': 2,
            'zfs.list_hits': 4,
            'zfs.arc_size_breakdown': 2,
            'zfs.important_ops': 4,
            'zfs.actual_hits': 2,
            'zfs.actual_hits_rate': 2,
            'zfs.demand_data_hits': 2,
            'zfs.demand_data_hits_rate': 2,
            'zfs.prefetch_data_hits': 2,
            'zfs.prefetch_data_hits_rate': 2,
            'zfs.hash_elements': 2,
            'zfs.hash_chains': 2,

            # k8s pods stats
            'k8s_cpu': K8S_PODS_COUNT,
            'k8s_mem': K8S_PODS_COUNT,
            'k8s_net': K8S_PODS_COUNT * 2,

            # cputemp
            'cputemp.temperatures': core_count,

            # ups
            'nut_ups.charge': 1,
            'nut_ups.runtime': 1,
            'nut_ups.battery_voltage': 4,
            'nut_ups.input_voltage': 3,
            'nut_ups.input_current': 1,
            'nut_ups.input_frequency': 2,
            'nut_ups.output_voltage': 1,
            'nut_ups.load': 1,
            'nut_ups.temp': 1,
            'netdata.plugin_chartsd_nut': 1,
        },
        60: {  # smartd_logs
            'smart_log.temperature_celsius': disk_count}
    }
    return {
        sec: sum(d.values()) for sec, d in data.items()
    }
