from collections import namedtuple
import re
import time

RE_NVME_C = re.compile(r"(nvme[0-9]+)c[0-9]+(n[0-9]+)")
RE_NVME_P = re.compile(r"(nvme[0-9]+n[0-9]+)p[0-9]+")

DiskStat = namedtuple("DiskStat", ["rd_ios", "rd_bytes", "wr_ios", "wr_bytes", "tot_ticks"])


def get_device_disk(disk):
    # Strip partition numbers and NVMe namespaces
    # Disks are reported above partitions and NVMe namespaces are reported above NVMe devices
    # They are the ones that contain corresponding device stats so we'll parse the first
    # line we see and skip the rest (which would be zeroes)
    if disk.startswith("nvme"):
        disk = RE_NVME_C.sub(r"\1\2", disk)
        disk = RE_NVME_P.sub(r"\1", disk)
    else:
        while disk and disk[-1].isdigit():
            disk = disk[:-1]

    return disk


class DiskStats:
    def __init__(self):
        self.prev = None
        self.prev_time = None
        self.current = None
        self.current_time = None
        self._read()

    def _read(self):
        with open("/proc/diskstats") as f:
            lines = f.readlines()

        self.current = {}
        for line in lines:
            line = line.split()

            disk = line[2]

            if disk.startswith("loop"):
                continue

            disk = get_device_disk(disk)
            if disk in self.current:
                continue

            # According to https://github.com/torvalds/linux/blob/7ca8cf5/include/linux/types.h#L120
            # sectors are always 512 bytes.
            disk_stat = DiskStat(
                rd_ios=int(line[3]),
                rd_bytes=int(line[5]) * 512,
                wr_ios=int(line[7]),
                wr_bytes=int(line[9]) * 512,
                tot_ticks=int(line[12]),
            )

            self.current[disk] = disk_stat

        self.current_time = time.monotonic()

    def get(self):
        self.prev = self.current
        self.prev_time = self.current_time
        self._read()

        read_ops = 0
        read_bytes = 0
        write_ops = 0
        write_bytes = 0
        total_ticks = 0
        count = 0
        for disk, current in self.current.items():
            prev = self.prev.get(disk)
            if prev is None:
                continue

            read_ops += current.rd_ios - prev.rd_ios
            read_bytes += current.rd_bytes - prev.rd_bytes
            write_ops += current.wr_ios - prev.wr_ios
            write_bytes += current.wr_bytes - prev.wr_bytes
            total_ticks += current.tot_ticks - prev.tot_ticks
            count += 1

        t = self.current_time - self.prev_time

        return {
            "read_ops": int(read_ops / t),
            "read_bytes": int(read_bytes / t),
            "write_ops": int(write_ops / t),
            "write_bytes": int(write_bytes / t),
            "busy": total_ticks / count / 1000 / t,
        }
