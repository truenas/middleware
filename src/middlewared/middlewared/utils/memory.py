from typing import TypedDict

__all__ = ('get_memory_info')


class MemoryInfo(TypedDict):
    total: int
    """Total amount of memory in bytes"""
    available: int
    """Total available memory in bytes"""


def get_memory_info() -> MemoryInfo:
    total = avail = 0
    with open('/proc/meminfo') as f:
        for line in f:
            if total and avail:
                break

            if not total and 'MemTotal' in line:
                total = int(line.split()[1]) * 1024
                continue

            if not avail and 'MemAvailable' in line:
                avail = int(line.split()[1] * 1024)
                continue

    return MemoryInfo(total=total, available=avail)
