from bases.FrameworkServices.SimpleService import SimpleService

from middlewared.utils.disks_.disk_class import iterate_disks


class Service(SimpleService):
    def __init__(self, configuration=None, name=None):
        SimpleService.__init__(self, configuration=configuration, name=name)
        self.update_every = 300
        self.disks = set()

    def check(self):
        self.add_disks_to_charts([d.identifier for d in iterate_disks()])
        return True

    def get_data(self):
        disks_temps = {}
        new_disks = []
        for disk in iterate_disks():
            # We do this to handle the case when a disk was replaced with another one or a new one was added
            # Essentially what we want to ensure is that any new disk which has been added exists in the netdata
            # database correctly
            if disk.identifier not in self.disks:
                new_disks.append(disk.identifier)

            disks_temps[f'{disk.identifier}.temp'] = disk.temp().temp_c or 0

        self.add_disks_to_charts(new_disks)
        return disks_temps

    def add_disks_to_charts(self, disk_ids):
        for disk_id in disk_ids:
            if disk_id in self.charts:
                continue

            self.charts.add_chart([
                disk_id, disk_id, disk_id, 'Celsius',
                'disk.temp',
                f'Temperature for {disk_id} disk',
                'line',
            ])
            self.charts[disk_id].add_dimension([f'{disk_id}.temp', 'temp', 'absolute'])
            self.disks.add(disk_id)
