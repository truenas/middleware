from middlewared.service import CallError
from middlewared.schema import Dict, Str

from .device import Device
from .utils import create_element, LIBVIRT_URI


class USB(Device):

    schema = Dict(
        'attributes',
        Str('device', required=True, empty=False),
    )

    @property
    def usb_device(self):
        return self.data['attributes']['device']

    def identity(self):
        return self.usb_device

    def get_vms_using_device(self):
        devs = self.middleware.call_sync(
            'vm.device.query', [['attributes.device', '=', self.usb_device], ['dtype', '=', 'USB']]
        )
        return self.middleware.call_sync('vm.query', [['id', 'in', [dev['vm'] for dev in devs]]])

    def get_details(self):
        return self.middleware.call_sync('vm.device.usb_passthrough_device', self.usb_device)

    def is_available(self):
        return self.get_details()['available']


