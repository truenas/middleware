def calculate_cpu_usage(cpu_times: list[int]) -> float:
    """
    Calculate CPU usage as a percentage.
    Excludes 'idle' and 'iowait' times from the calculation.

    Args:
        cpu_times (list[int]): List of CPU time values.

    Returns:
        float: CPU usage percentage, rounded to two decimal places.
    """
    total_time = sum(cpu_times)
    if total_time:
        idle_time = cpu_times[3]  # Idle
        iowait_time = cpu_times[4]  # I/O Wait
        active_time = total_time - idle_time - iowait_time
        return round((active_time / total_time) * 100, 2)
    return 0.0


def get_cpu_usage() -> dict[str, float]:
    """
    Retrieve CPU usage statistics from /proc/stat.

    Returns:
        dict[str, float]: Dictionary containing CPU usage percentages for
            the aggregate ('cpu') and each individual core ('cpu0', 'cpu1', ...).
    """
    cpu_usage_data = {}
    with open('/proc/stat') as f:
        # Process only CPU-related lines
        for line in filter(lambda x: x.startswith('cpu'), f):
            # core == 'cpu' | 'cpu0', 'cpu1' etc, with the
            # former representing the aggregate numbers of
            # all cpu cores and the later representing the
            # cpu core specific values
            core, values = line.split(' ', 1)
            cpu_usage_data[core] = calculate_cpu_usage(
                list(map(int, values.strip().split()))
            )
    return cpu_usage_data
