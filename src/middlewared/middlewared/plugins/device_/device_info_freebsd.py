import re

from bsd.devinfo import DevInfo
from .device_info_base import DeviceInfoBase
from middlewared.common.camcontrol import camcontrol_list
from middlewared.service import Service


RE_DISK_NAME = re.compile(r'^([a-z]+)([0-9]+)$')


class DeviceService(Service, DeviceInfoBase):

    async def get_disks(self):
        return {
            k: v for k, v in (await self.middleware.call('geom.cache.get_disks')).items()
            if not k.startswith('multipath/')
        }

    async def get_disk(self, name):
        return (await self.middleware.call('geom.cache.get_disks')).get(name)

    async def get_serials(self):
        ports = []
        for devices in DevInfo().resource_managers['I/O ports'].values():
            for dev in devices:
                if not dev.name.startswith('uart'):
                    continue
                port = self.serial_port_default.copy()
                port.update({
                    'name': dev.name,
                    'description': dev.desc,
                    'drivername': dev.drivername,
                    'location': dev.location,
                    'start': hex(dev.start),
                    'size': dev.size
                })
                ports.append(port)
        return ports

    async def get_storage_devices_topology(self):
        return await camcontrol_list()
