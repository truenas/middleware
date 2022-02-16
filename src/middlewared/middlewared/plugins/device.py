from middlewared.schema import accepts, Str
from middlewared.service import Service, private
from bsd.devinfo import DevInfo


class DeviceService(Service):

    @accepts(Str('type', enum=['SERIAL', 'DISK']))
    async def get_info(self, _type):
        """
        Get info for SERIAL/DISK device types.
        """
        return await self.middleware.call(f'device.get_{_type.lower()}s')

    @private
    async def get_disks(self):
        return {
            k: v for k, v in (await self.middleware.call('geom.cache.get_disks')).items()
            if not k.startswith('multipath/')
        }

    @private
    async def get_disk(self, name):
        return (await self.middleware.call('geom.cache.get_disks')).get(name)

    @private
    async def get_serials(self):
        ports = []
        for devices in DevInfo().resource_managers['I/O ports'].values():
            for dev in devices:
                if not dev.name.startswith('uart'):
                    continue
                port = {
                    'name': dev.name,
                    'description': dev.desc,
                    'drivername': dev.drivername,
                    'location': dev.location,
                    'start': hex(dev.start),
                    'size': dev.size
                }
                ports.append(port)
        return ports

    @private
    async def get_storage_devices_topology(self):
        return await self.middleware.call('geom.cache.get_topology')
