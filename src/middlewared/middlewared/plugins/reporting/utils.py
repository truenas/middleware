import collections
import contextlib
import os.path
import typing

from middlewared.plugins.system_dataset.utils import SYSDATASET_PATH

from .netdata.graph_base import GraphBase


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


def get_netdata_state_path() -> str:
    return os.path.join(SYSDATASET_PATH, 'netdata/ix_state')


def get_metrics_approximation(
    disk_count: int, core_count: int, interface_count: int, pool_count: int, vms_count: int,
    systemd_service_count: int, containers_count: typing.Optional[int] = 10,
) -> dict:
    data = {
        1: {
            'system.clock_sync_state': 1,
            'system.clock_status': 2,
            'system.clock_sync_offset': 1,

            # diskstats
            'system.io': 2,
            'truenas_disk_stats.ops': 2 * disk_count,
            'truenas_disk_stats.io': 2 * disk_count,
            'truenas_disk_stats.busy': 1 * disk_count,

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

            # meminfo
            'truenas_meminfo': 2,

            # uptime
            'system.uptime': 1,

            # loadavg
            'system.load': 3,
            'system.active_processes': 1,

            # zfs arcstats
            'truenas_arcstats.free': 1,
            'truenas_arcstats.avail': 1,
            'truenas_arcstats.size': 1,
            'truenas_arcstats.dread': 1,
            'truenas_arcstats.ddread': 1,
            'truenas_arcstats.dmread': 1,
            'truenas_arcstats.ddhit': 1,
            'truenas_arcstats.ddioh': 1,
            'truenas_arcstats.ddmis': 1,
            'truenas_arcstats.ddh_p': 1,
            'truenas_arcstats.ddi_p': 1,
            'truenas_arcstats.ddm_p': 1,
            'truenas_arcstats.dmhit': 1,
            'truenas_arcstats.dmioh': 1,
            'truenas_arcstats.dmmis': 1,
            'truenas_arcstats.dmh_p': 1,
            'truenas_arcstats.dmi_p': 1,
            'truenas_arcstats.dmm_p': 1,
            'truenas_arcstats.l2hits': 1,
            'truenas_arcstats.l2miss': 1,
            'truenas_arcstats.l2read': 1,
            'truenas_arcstats.l2hit_p': 1,
            'truenas_arcstats.l2miss_p': 1,
            'truenas_arcstats.l2bytes': 1,
            'truenas_arcstats.l2wbytes': 1,

            # cpu usage, it is core count + 1 with +1 saving aggregated stats
            'cpu.usage': core_count + 1,

            # cputemp
            'cputemp.temperatures': core_count + 1,

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

            # cgroups
            'services.io_ops_write': systemd_service_count,
            'services.io_ops_read': systemd_service_count,
            'services.io_write': systemd_service_count,
            'services.io_read': systemd_service_count,
            'services.mem_usage': systemd_service_count,
            'services.cpu': systemd_service_count,
            'cgroup_qemu_vm.cpu_limit': vms_count,
            'cgroup_qemu_vm.cpu': 2 * vms_count,
            'cgroup_qemu_vm.throttled': vms_count,
            'cgroup_qemu_vm.throttled_duration': vms_count,
            'cgroup_qemu_vm.mem': 6 * vms_count,
            'cgroup_qemu_vm.writeback': 2 * vms_count,
            'cgroup_qemu_vm.pgfaults': 2 * vms_count,
            'cgroup_qemu_vm.mem_usage': 2 * vms_count,
            'cgroup_qemu_vm.mem_usage_limit': 2 * vms_count,
            'cgroup_qemu_vm.mem_utilization': vms_count,
            'cgroup_qemu_vm.io': 2 * vms_count,
            'cgroup_qemu_vm.serviced_ops': 2 * vms_count,
            'cgroup_qemu_vm.cpu_some_pressure': 3 * vms_count,
            'cgroup_qemu_vm.cpu_some_pressure_stall_time': vms_count,
            'cgroup_qemu_vm.cpu_full_pressure': 3 * vms_count,
            'cgroup_qemu_vm.cpu_full_pressure_stall_time': vms_count,
            'cgroup_qemu_vm.mem_some_pressure': 3 * vms_count,
            'cgroup_qemu_vm.memory_some_pressure_stall_time': vms_count,
            'cgroup_qemu_vm.mem_full_pressure': 3 * vms_count,
            'cgroup_qemu_vm.memory_full_pressure_stall_time': vms_count,
            'cgroup_qemu_vm.io_some_pressure': 3 * vms_count,
            'cgroup_qemu_vm.io_some_pressure_stall_time': vms_count,
            'cgroup_qemu_vm.io_full_pressure': 3 * vms_count,
            'cgroup_qemu_vm.io_full_pressure_stall_time': vms_count,

            'cgroup_hash.cpu_limit': containers_count,
            'cgroup_hash.cpu': 2 * containers_count,
            'cgroup_hash.throttled': containers_count,
            'cgroup_hash.throttled_duration': containers_count,
            'cgroup_hash.mem': 6 * containers_count,
            'cgroup_hash.writeback': 2 * containers_count,
            'cgroup_hash.pgfaults': 2 * containers_count,
            'cgroup_hash.mem_usage': 2 * containers_count,
            'cgroup_hash.mem_usage_limit': 2 * containers_count,
            'cgroup_hash.mem_utilization': containers_count,
            'cgroup_hash.cpu_some_pressure': 3 * containers_count,
            'cgroup_hash.cpu_some_pressure_stall_time': containers_count,
            'cgroup_hash.cpu_full_pressure': 3 * containers_count,
            'cgroup_hash.cpu_full_pressure_stall_time': containers_count,
            'cgroup_hash.mem_some_pressure': 3 * containers_count,
            'cgroup_hash.memory_some_pressure_stall_time': containers_count,
            'cgroup_hash.mem_full_pressure': 3 * containers_count,
            'cgroup_hash.memory_full_pressure_stall_time': containers_count,
            'cgroup_hash.io_some_pressure': 3 * containers_count,
            'cgroup_hash.io_some_pressure_stall_time': containers_count,
            'cgroup_hash.io_full_pressure': 3 * containers_count,
            'cgroup_hash.io_full_pressure_stall_time': containers_count,
        },
        300: {
            # disk temp logs
            'truenas_disk_temp.temp': disk_count,
            # pool usage
            'truenas_pool.usage': pool_count * 3,
        }
    }
    return {
        sec: sum(d.values()) for sec, d in data.items()
    }
