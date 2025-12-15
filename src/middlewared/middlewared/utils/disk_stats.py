import contextlib
import logging

from .disks_.disk_class import iterate_disks


# always 512 on Linux
# https://github.com/torvalds/linux/blob/daa121128a2d2ac6006159e2c47676e4fcd21eab/include/linux/blk_types.h#L25-L34
# Basically /proc/diskstats reports read/write sector counts in fixed 512 byte units independent of the
# underlying device's logical/physical sector size which is why we use the fixed constant/sector size here
# reflecting how it is already being done in /proc/diskstats
SECTOR_SIZE = 512


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
                    'reads': (read_sectors * SECTOR_SIZE) / 1024,  # convert to kb
                    'writes': (write_sectors * SECTOR_SIZE) / 1024,  # convert to kb
                    'read_ops': read_ops,
                    'write_ops': write_ops,
                    'busy': busy_time,
                }

    return stats
