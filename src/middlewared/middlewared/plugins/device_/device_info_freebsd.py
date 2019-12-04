from bsd import geom, devinfo

from .device_info_base import DeviceInfoBase
from middlewared.service import Service


class DeviceService(Service, DeviceInfoBase):

    async def get_disk(self):
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
            }
            if g.provider.config:
                disk.update(g.provider.config)
            disks[g.name] = disk
        return disks

    async def get_serial(self):
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
