from psutil import disk_io_counters
from statistics import mean


class DiskStats:
    def __init__(self):
        self.disks = ('ada', 'da', 'nvd')

    def read(self):
        read_ops = []
        read_bytes = []
        write_ops = []
        write_bytes = []
        busy = []
        cur_values = disk_io_counters(perdisk=True, nowrap=True)
        for disk, current in filter(lambda x: x[0].startswith(self.disks), cur_values.items()):
            read_ops.append(current.read_count)
            read_bytes.append(current.read_bytes)
            write_ops.append(current.write_count)
            write_bytes.append(current.write_bytes)
            busy.append(current.busy_time)

        return {
            "read_ops": mean(read_ops),
            "read_bytes": mean(read_bytes),
            "write_ops": mean(write_ops),
            "write_bytes": mean(write_bytes),
            "busy": mean(busy)
        }
