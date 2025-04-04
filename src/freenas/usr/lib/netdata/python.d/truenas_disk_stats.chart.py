from bases.FrameworkServices.SimpleService import SimpleService

from middlewared.utils.disk_stats import get_disk_stats


class Service(SimpleService):
    def __init__(self, configuration=None, name=None):
        SimpleService.__init__(self, configuration=configuration, name=name)
        self.disk_mapping = {}
        self.added_disks = set()

    def check(self):
        return True

    def get_data(self):
        disks_stats = {}
        disks_to_add = set()
        for disk_id, disks_io in get_disk_stats().items():
            for op, value in disks_io.items():
                disks_stats[f'{disk_id}.{op}'] = value
            if disk_id not in self.added_disks:
                disks_to_add.add(disk_id)

        self.add_disk_to_charts(disks_to_add)
        return disks_stats

    def add_disk_to_charts(self, disk_ids):
        for disk_id in disk_ids:
            if disk_id in self.charts:
                continue

            self.charts.add_chart([
                f'io.{disk_id}', disk_id, disk_id, 'KiB/s',
                'disk.io',
                f'Read/Write for disk {disk_id}',
                'line',
            ])
            self.charts.add_chart([
                f'ops.{disk_id}', disk_id, disk_id, 'Operation/s',
                'disk.ops',
                f'Complete read/write for disk {disk_id}',
                'line',
            ])
            self.charts.add_chart([
                f'busy.{disk_id}', disk_id, disk_id, 'Milliseconds',
                'disk.busy',
                'Disk Busy Time',
                'area',
            ])
            self.charts[f'io.{disk_id}'].add_dimension([f'{disk_id}.reads', 'reads', 'incremental'])
            self.charts[f'io.{disk_id}'].add_dimension([f'{disk_id}.writes', 'writes', 'incremental'])
            self.charts[f'ops.{disk_id}'].add_dimension([f'{disk_id}.read_ops', 'read_ops', 'incremental'])
            self.charts[f'ops.{disk_id}'].add_dimension([f'{disk_id}.write_ops', 'write_ops', 'incremental'])
            self.charts[f'busy.{disk_id}'].add_dimension([f'{disk_id}.busy', 'busy', 'incremental'])

            self.added_disks.add(disk_id)
