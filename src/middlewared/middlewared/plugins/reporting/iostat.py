from psutil import disk_io_counters


class DiskStats:
    def __init__(self, interval):
        self.interval = interval
        self.disks = ('ada', 'da', 'nvd')

    def read(self):
        read_ops = read_bytes = write_ops = write_bytes = busy = total_disks = 0
        cur_values = disk_io_counters(perdisk=True, nowrap=False)
        for disk, current in filter(lambda x: x[0].startswith(self.disks), cur_values.items()):
            read_ops += current.read_count
            read_bytes += current.read_bytes
            write_ops += current.write_count
            write_bytes += current.write_bytes
            busy += float(current.busy_time) / self.interval

        return {
            "read_ops": read_ops,
            "read_bytes": read_bytes,
            "write_ops": write_ops,
            "write_bytes": write_bytes,
            "busy": busy / total_disks if total_disks else 0
        }
