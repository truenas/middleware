import typing

from .utils import normalize_value, safely_retrieve_dimension


def get_disk_stats(netdata_metrics: dict, disks: typing.List[str]) -> dict:
    total_disks = len(disks)
    read_ops = read_bytes = write_ops = write_bytes = busy = 0
    for disk in disks:
        read_ops += safely_retrieve_dimension(netdata_metrics, f'disk_ops.{disk}', 'reads', 0)
        read_bytes += normalize_value(
            safely_retrieve_dimension(netdata_metrics, f'disk.{disk}', 'reads', 0), multiplier=1024,
        )
        write_ops += normalize_value(safely_retrieve_dimension(netdata_metrics, f'disk_ops.{disk}', 'writes', 0))
        write_bytes += normalize_value(safely_retrieve_dimension(netdata_metrics, f'disk.{disk}', 'writes', 0))
        busy += safely_retrieve_dimension(netdata_metrics, f'disk_busy.{disk}', 'busy', 0)

    return {
        'read_ops': read_ops,
        'read_bytes': read_bytes,
        'write_ops': write_ops,
        'write_bytes': write_bytes,
        'busy': busy / total_disks if total_disks else 0,
    }
