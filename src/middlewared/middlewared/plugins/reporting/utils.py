def calculate_disk_space_for_netdata(metrics: int, days: int) -> int:
    # Constants
    sec_per_day = 86400
    points_per_metric_per_day = sec_per_day * days
    bytes_per_point = 1

    # Calculate required disk space in bytes
    required_disk_space_bytes = metrics * points_per_metric_per_day * bytes_per_point

    # Convert bytes to megabytes (1 MB = 1024 * 1024 bytes)
    required_disk_space_mb = required_disk_space_bytes / (1024 * 1024)

    return int(required_disk_space_mb)


def convert_unit(unit: str, page: int) -> int:
    return {
        'HOUR': 60,
        'DAY': 60 * 24,
        'WEEK': 60 * 24 * 7,
        'MONTH': 60 * 24 * 30,
        'YEAR': 60 * 24 * 365,
    }[unit] * page


def get_metrics_approximation(disk_count: int, core_count: int, interface_count: int, pool_count: int) -> dict:
    return {
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

        # cputemp
        'cputemp.temperatures': core_count,

        # smartd_logs
        'smart_log.temperature_celsius': disk_count,
    }
