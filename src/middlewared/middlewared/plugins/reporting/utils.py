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
