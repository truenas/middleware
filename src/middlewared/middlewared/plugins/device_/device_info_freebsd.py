import re

from bsd import geom, devinfo

from .device_info_base import DeviceInfoBase
from middlewared.service import Service


RE_DISK_NAME = re.compile(r'^([a-z]+)([0-9]+)$')


class DeviceService(Service, DeviceInfoBase):

    async def get_disks(self):
        await self.middleware.run_in_thread(geom.scan)
        disks = {}
        klass = geom.class_by_name('DISK')
        if not klass:
            return disks
        for g in klass.geoms:
            # Skip cd*
            if g.name.startswith('cd'):
                continue
            disk = self.disk_default.copy()
            disk.update({
                'name': g.name,
                'mediasize': g.provider.mediasize,
                'sectorsize': g.provider.sectorsize,
                'stripesize': g.provider.stripesize,
            })
            if g.provider.config:
                disk.update({k: v for k, v in g.provider.config.items() if k not in ('fwheads', 'fwsectors')})
                if disk['rotationrate'] is not None:
                    disk['rotationrate'] = int(disk['rotationrate']) if disk['rotationrate'].isdigit() else None
                if disk['descr'] is not None and not disk['descr']:
                    disk['descr'] = None
                disk['model'] = disk['descr']

                if disk['rotationrate'] is not None:
                    if disk['rotationrate'] == 0:
                        disk['rotationrate'] = None
                        disk['type'] = 'SSD'
                    else:
                        disk['type'] = 'HDD'

            if not disk['ident']:
                output = await self.middleware.call('disk.smartctl', g.name, ['-i'], {'cache': False, 'silent': True})
                if output:
                    search = self.RE_SERIAL_NUMBER.search(output)
                    if search:
                        disk['ident'] = search.group('serial')

            if not disk['ident']:
                disk['ident'] = ''

            reg = RE_DISK_NAME.search(g.name)
            if reg:
                disk['subsystem'] = reg.group(1)
                disk['number'] = int(reg.group(2))

            # We still keep ident/mediasize to not break previous api users
            disk['serial'] = disk['ident']
            disk['size'] = disk['mediasize']

            disks[g.name] = disk
        return disks

    async def get_serials(self):
        ports = []
        for devices in devinfo.DevInfo().resource_managers['I/O ports'].values():
            for dev in devices:
                if not dev.name.startswith('uart'):
                    continue
                ports.append({
                    'name': dev.name,
                    'description': dev.desc,
                    'drivername': dev.drivername,
                    'location': dev.location,
                    'start': hex(dev.start),
                    'size': dev.size
                })
        return ports
