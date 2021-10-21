from bsd.devinfo import DevInfo
from middlewared.schema import private, accepts, Str
from middlewared.service import Service
from middlewared.common.camcontrol import camcontrol_list


class DeviceService(Service):

    @accepts(Str('type', enum=['SERIAL', 'DISK']))
    async def get_info(self, _type):
        """
        Get info for SERIAL/DISK device types.
        """
        return await self.middleware.call(f'device.get_{_type.lower()}s')

    @private
    async def get_disks(self, from_cache):
        return await self.middleware.call('geom.get_disks')

    @private
    async def get_disk(self, name):
        return (await self.middleware.call('geom.get_disks')).get(name, None)

    @private
    async def get_serials(self):
        ports = []
        for devices in DevInfo().resource_managers['I/O ports'].values():
            for dev in devices:
                if not dev.name.startswith('uart'):
                    continue
                else:
                    ports.append({
                        'name': dev.name or None,
                        'description': dev.desc or None,
                        'drivername': dev.drivername or 'uart',
                        'location': dev.location or None,
                        'start': hex(dev.start) or None,
                        'size': dev.size or None,
                    })

        return ports

    async def get_storage_devices_topology(self):
        return await camcontrol_list()
