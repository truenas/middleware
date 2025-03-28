import contextlib
import logging
import os

from .disks_.disk_class import iterate_disks


logger = logging.getLogger(__name__)


def get_disk_stats() -> dict[str, dict]:
    available_disks = {d.name: d for d in iterate_disks()}
    stats = {}
    with contextlib.suppress(IOError):
        with open('/proc/diskstats', 'r') as disk_stats_fd:
            for entry in disk_stats_fd:
                parts = entry.strip().split()
                if len(parts) < 14:
                    continue  # skip lines that don't have all the fields

                disk_name = parts[2]
                if disk_name not in available_disks:
                    continue

                sector_size = 512  # default sector size if we are not able to find it keeping in line with netdata
                with contextlib.suppress(FileNotFoundError, ValueError):
                    with open(os.path.join('/sys/block', disk_name, 'queue/hw_sector_size'), 'r') as f:
                        sector_size = int(f.read().strip())

                try:
                    read_ops = int(parts[3])
                    read_sectors = int(parts[5])
                    write_ops = int(parts[7])
                    write_sectors = int(parts[9])
                    busy_time = int(parts[12])
                except (IndexError, ValueError) as e:
                    logger.error('Failed to parse disk stats for %r: %r', disk_name, e)
                    continue

                stats[available_disks[disk_name].identifier] = {
                    'reads': (read_sectors * sector_size) / 1024,  # convert to kb
                    'writes': (write_sectors * sector_size) / 1024,  # convert to kb
                    'read_ops': read_ops,
                    'write_ops': write_ops,
                    'busy': busy_time,
                }

    return stats
