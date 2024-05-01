from middlewared.schema import accepts, Bool, Dict, Int, List, OROperator, returns, Str
from middlewared.service import Service


class DeviceService(Service):

    class Config:
        cli_namespace = 'system.device'

    @accepts(
        Dict(
            'data',
            Str('type', enum=['SERIAL', 'DISK', 'GPU'], required=True),
            Bool('get_partitions', required=False, default=False),
            Bool('serials_only', required=False, default=False),
        ),
        roles=['READONLY_ADMIN']
    )
    @returns(OROperator(
        List('serial_info', items=[Dict(
            'serial_info',
            Str('name', required=True),
            Str('location'),
            Str('drivername'),
            Str('start'),
            Int('size'),
            Str('description'),
        )]),
        List('gpu_info', items=[Dict(
            'gpu_info',
            Dict(
                'addr',
                Str('pci_slot', required=True),
                Str('domain', required=True),
                Str('bus', required=True),
                Str('slot', True),
            ),
            Str('description', required=True),
            List('devices', items=[Dict(
                'gpu_device',
                Str('pci_id', required=True),
                Str('pci_slot', required=True),
                Str('vm_pci_slot', required=True),
            )]),
            Str('vendor', required=True, null=True),
            Bool('available_to_host', required=True),
            Bool('uses_system_critical_devices', required=True),
        ),
        ]),
        Dict('disk_info', additional_attrs=True),
        name='device_info',
    ))
    async def get_info(self, data):
        """
        Get info for `data['type']` device.

        If `type` is "DISK":
            `get_partitions`: boolean, when set to True will query partition
                information for the disks. NOTE: this can be expensive on
                systems with a large number of disks present.
            `serials_only`: boolean, when set to True will query serial information
                _ONLY_ for the disks.
        """
        method = f'device.get_{data["type"].lower()}s'
        if method == 'device.get_disks':
            return await self.middleware.call(method, data['get_partitions'], data['serials_only'])
        return await self.middleware.call(method)
