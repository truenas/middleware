from middlewared.utils.disks_.disk_class import DiskEntry

from .utils import normalize_value, safely_retrieve_dimension


def get_disk_stats(netdata_metrics: dict, disks: list[DiskEntry], disk_mapping: dict[str, str]) -> dict:
    total_disks = len(disks)
    read_ops = read_bytes = write_ops = write_bytes = busy = 0
    for disk in disks:
        mapped_key = disk_mapping.get(disk.name)
        read_ops += safely_retrieve_dimension(
            netdata_metrics, f'truenas_disk_stats.ops.{mapped_key}', f'{mapped_key}.read_ops', 0
        )
        read_bytes += normalize_value(
            safely_retrieve_dimension(
                netdata_metrics, f'truenas_disk_stats.io.{mapped_key}', f'{mapped_key}.reads', 0
            ), multiplier=1024,
        )
        write_ops += normalize_value(safely_retrieve_dimension(
            netdata_metrics, f'truenas_disk_stats.ops.{mapped_key}', f'{mapped_key}.write_ops', 0
        ))
        write_bytes += normalize_value(
            safely_retrieve_dimension(
                netdata_metrics, f'truenas_disk_stats.io.{mapped_key}', f'{mapped_key}.writes', 0
            ), multiplier=1024,
        )
        busy += safely_retrieve_dimension(
            netdata_metrics, f'truenas_disk_stats.busy.{mapped_key}', f'{mapped_key}.busy', 0
        )

    return {
        'read_ops': read_ops,
        'read_bytes': read_bytes,
        'write_ops': write_ops,
        'write_bytes': write_bytes,
        'busy': busy / total_disks if total_disks else 0,
    }
