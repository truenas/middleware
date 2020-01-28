from middlewared.schema import accepts, Str
from middlewared.service import Service


class DeviceService(Service):

    @accepts(Str('type', enum=['SERIAL', 'DISK']))
    async def get_info(self, _type):
        """
        Get info for SERIAL/DISK device types.
        """
        return await self.middleware.call(f'device.get_{_type.lower()}s')
