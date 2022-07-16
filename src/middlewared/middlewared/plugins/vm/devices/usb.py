from middlewared.service import CallError
from middlewared.schema import Dict, Str

from .device import Device
from .utils import create_element, LIBVIRT_URI


class USB(Device):

    schema = Dict(
        'attributes',
        Str('device', required=True, empty=False),
    )

    def usb_device(self):
        return self.data['attributes']['device']
