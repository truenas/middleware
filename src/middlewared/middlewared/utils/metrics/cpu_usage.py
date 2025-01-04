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
    aggregate_times = []  # Holds time data for all CPUs combined

    with open('/proc/stat') as f:
        # Process only CPU-related lines
        for line in filter(lambda x: x.startswith('cpu'), f):
            fields = line.split()
            cpu_times = [int(value) for value in fields[1:]]  # Convert times to integers

            if fields[0] == 'cpu':  # Aggregate CPU line
                aggregate_times = cpu_times
            else:  # Individual CPU core lines (e.g., 'cpu0', 'cpu1', ...)
                # Calculate usage for each core
                cpu_usage_data[fields[0]] = calculate_cpu_usage(cpu_times)

    # Calculate aggregate CPU usage
    cpu_usage_data['cpu'] = calculate_cpu_usage(aggregate_times)

    return cpu_usage_data
