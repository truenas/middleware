from middlewared.schema import accepts, Str
from middlewared.service import Service


class DeviceService(Service):

    class Config:
        cli_namespace = 'system.device'

    @accepts(Str('type', enum=['SERIAL', 'DISK', 'GPU']))
    async def get_info(self, _type):
        """
        Get info for SERIAL/DISK/GPU device types.
        """
        return await self.middleware.call(f'device.get_{_type.lower()}s')
