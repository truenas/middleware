from middlewared.schema import accepts, Bool, Dict, Int, List, OROperator, returns, Str
from middlewared.service import Service


class DeviceService(Service):

    class Config:
        cli_namespace = 'system.device'

    @accepts(Str('type', enum=['SERIAL', 'DISK', 'GPU']))
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
        ),
        ]),
        Dict('disk_info', additional_attrs=True),
        name='device_info',
    ))
    async def get_info(self, _type):
        """
        Get info for SERIAL/DISK/GPU device types.
        """
        return await self.middleware.call(f'device.get_{_type.lower()}s')
