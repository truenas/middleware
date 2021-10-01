from psutil import disk_io_counters


class DiskStats:
    def __init__(self, interval, prev_data):
        self.interval = interval
        self.prev_data = prev_data
        self.disks = ('ada', 'da', 'nvd')

    def read(self):
        read_ops = read_bytes = write_ops = write_bytes = busy = total_disks = 0
        for disk, current in filter(lambda x: x[0].startswith(self.disks), disk_io_counters(perdisk=True).items()):
            read_ops += current.read_count
            read_bytes += current.read_bytes
            write_ops += current.write_count
            write_bytes += current.write_bytes
            busy += float(current.busy_time) / self.interval
            total_disks += 1

        # the current cumulative data
        curr_data = {
            'read_ops': read_ops,
            'read_bytes': read_bytes,
            'write_ops': write_ops,
            'write_bytes': write_bytes,
            'busy': busy / total_disks if total_disks else 0
        }

        # the difference between curr_data and prev_data
        new_data = {
            'read_ops': curr_data['read_ops'] - self.prev_data.get('read_ops', 0),
            'read_bytes': curr_data['read_bytes'] - self.prev_data.get('read_bytes', 0),
            'write_ops': curr_data['write_ops'] - self.prev_data.get('write_ops', 0),
            'write_bytes': curr_data['write_bytes'] - self.prev_data.get('write_bytes', 0),
            'busy': curr_data['busy'] - self.prev_data.get('busy', 0),
        }

        return curr_data, new_data
