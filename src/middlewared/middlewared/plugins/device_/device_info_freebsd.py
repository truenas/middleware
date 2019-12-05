from bsd import geom, devinfo

from .device_info_base import DeviceInfoBase
from middlewared.service import Service


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
            disk = {
                'name': g.name,
                'mediasize': g.provider.mediasize,
                'sectorsize': g.provider.sectorsize,
                'stripesize': g.provider.stripesize,
                'fwheads': None,
                'fwsectors': None,
                'rotationrate': None,
                'ident': None,
                'lunid': None,
                'descr': None,
                'subsystem': None,
                'number': None,
            }
            if g.provider.config:
                disk.update(g.provider.config)
            if not disk['ident']:
                output = await self.middleware.call('disk.smartctl', g.name, ['-i'], {'cache': False, 'silent': True})
                if output:
                    search = self.RE_SERIAL_NUMBER.search(output)
                    if search:
                        disk['ident'] = search.group('serial')

            reg = self.RE_DISK_NAME.search(g.name)
            if reg:
                disk['subsystem'] = reg.group(1)
                disk['number'] = int(reg.group(2))

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
