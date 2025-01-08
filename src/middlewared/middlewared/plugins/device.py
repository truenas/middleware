from middlewared.api import api_method
from middlewared.api.current import DeviceGetInfoArgs, DeviceGetInfoResult
from middlewared.service import Service


class DeviceService(Service):

    class Config:
        cli_namespace = 'system.device'

    @api_method(DeviceGetInfoArgs, DeviceGetInfoResult, roles=['READONLY_ADMIN'])
    async def get_info(self, data):
        """Get info for `type` device."""
        method = f'device.get_{data["type"].lower()}s'
        if method == 'device.get_disks':
            return await self.middleware.call(method, data['get_partitions'], data['serials_only'])
        return await self.middleware.call(method)
