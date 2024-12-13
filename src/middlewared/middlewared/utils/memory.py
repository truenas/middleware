from typing import TypedDict

__all__ = ('get_memory_info')


class MemoryInfo(TypedDict):
    total: int
    """Total available memory in bytes"""


def get_memory_info() -> MemoryInfo:
    total = 0
    with open('/proc/meminfo') as f:
        for line in filter(lambda x: 'MemTotal' in x, f):
            total = int(line.split()[1]) * 1024
            break

    return MemoryInfo(total=total)
