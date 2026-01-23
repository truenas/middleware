def calculate_cpu_usage(cur_cpu_times: list[int], old_cpu_times: list[int]) -> float:
    """
    Calculate CPU usage as a percentage.
    Excludes 'idle' and 'iowait' times from the calculation.

    Args:
        cur_cpu_times (list[int]): List of CPU time values.
        old_cpu_times (list[int]): List of CPU time values.

    Returns:
        float: CPU usage percentage, rounded to two decimal places.
    """
    delta_time = list(map(lambda args: args[0] - args[1], zip(cur_cpu_times, old_cpu_times)))
    total_time = sum(delta_time)
    if total_time:
        idle_time = delta_time[3]  # Idle
        iowait_time = delta_time[4]  # I/O Wait
        active_time = total_time - idle_time - iowait_time
        return round((active_time / total_time) * 100, 2)
    return 0.0


def get_cpu_usage(old_stats: dict[str, list[int]] | None = None) -> tuple[dict[str, float], dict[str, list[int]]]:
    """
    Retrieve CPU usage statistics from /proc/stat.

    Returns:
        dict[str, float]: Dictionary containing CPU usage percentages for
            the aggregate ('cpu') and each individual core ('cpu0', 'cpu1', ...).
    """
    # Calculation is inspired by how htop does it
    # https://github.com/htop-dev/htop/blob/3a9f468c626b9261dc3a5234fc362303aeb5103d/linux/Platform.c#L320
    old_stats = old_stats or {}
    cpu_usage_data = {}
    cached_values = {}
    with open('/proc/stat') as f:
        # Process only CPU-related lines
        for line in filter(lambda x: x.startswith('cpu'), f):
            # core == 'cpu' | 'cpu0', 'cpu1' etc, with the
            # former representing the aggregate numbers of
            # all cpu cores and the later representing the
            # cpu core specific values
            core, values = line.split(' ', 1)
            cpu_stats = list(map(int, values.strip().split()))
            cpu_usage_data[core] = calculate_cpu_usage(
                cpu_stats, old_stats.get(core, [0] * len(values))
            ) if old_stats else 0
            cached_values[core] = cpu_stats

    return cpu_usage_data, cached_values
