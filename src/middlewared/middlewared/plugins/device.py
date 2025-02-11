from middlewared.api import api_method
from middlewared.api.current import DeviceGetInfoArgs, DeviceGetInfoResult
from middlewared.service import Service
from middlewared.utils.serial import serial_port_choices


class DeviceService(Service):

    class Config:
        cli_namespace = 'system.device'

    @api_method(DeviceGetInfoArgs, DeviceGetInfoResult, roles=['READONLY_ADMIN'])
    async def get_info(self, data):
        """Get info for `type` device."""
        method = f'device.get_{data["type"].lower()}s'
        if method == 'device.get_disks':
            return await self.middleware.call(method, data['get_partitions'], data['serials_only'])
        elif method == 'device.get_serials':
            return await self.middleware.run_in_thread(serial_port_choices)
        return await self.middleware.call(method)
