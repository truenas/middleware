from psutil import disk_io_counters


class DiskStats:
    def __init__(self, interval, prev_data):
        self.interval = interval
        self.prev_data = prev_data
        self.ignore = ('sr', 'md', 'dm')

    def get_disk(self, disk):
        if disk.startswith(self.ignore):
            return
        elif disk.startswith('nvme'):
            if 'c' in disk or 'p' in disk:
                # nvme0c0p1 or nvme0n1p1 which reports statistics but we only
                # want the top-level namespace (i.e. nvme0n1) since it has the
                # over-all disk statistics
                return
            else:
                return disk
        else:
            while disk and disk[-1].isdigit():
                disk = disk[:-1]
            return disk

    def read(self):
        read_ops = read_bytes = write_ops = write_bytes = busy = total_disks = 0
        for disk, current in filter(lambda x: self.get_disk(x[0]) is not None, disk_io_counters(perdisk=True).items()):
            read_ops += current.read_count
            read_bytes += current.read_bytes
            write_ops += current.write_count
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
            'read_opts': curr_data['read_ops'] - self.prev_data.get('read_ops', 0),
            'read_bytes': curr_data['read_bytes'] - self.prev_data.get('read_bytes', 0),
            'write_ops': curr_data['write_ops'] - self.prev_data.get('write_ops', 0),
            'write_bytes': curr_data['write_bytes'] - self.prev_data.get('write_bytes', 0),
            'busy': curr_data['busy'] - self.prev_data.get('busy', 0),
        }

        return curr_data, new_data
