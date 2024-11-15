from dataclasses import dataclass


@dataclass(slots=True, frozen=True, kw_only=True)
class MemoryInfo:
    total: int


def get_memory_info() -> MemoryInfo:
    total = 0
    with open('/proc/meminfo') as f:
        for line in filter(lambda x: 'MemTotal' in x, f):
            total = int(line.split()[1]) * 1024
            break

        return MemoryInfo(
            total=total,
        )
