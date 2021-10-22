import os

from middlewared.schema import Dict, Str
from middlewared.validators import Match

from .device import Device
from .utils import create_element, disk_from_number


class CDROM(Device):

    schema = Dict(
        'attributes',
        Str('path', required=True, validators=[Match(r'^[^{}]*$')]),
    )

    def identity(self):
        return self.data['attributes']['path']

    def is_available(self):
        return os.path.exists(self.identity())

    def xml_linux(self, *args, **kwargs):
        disk_number = kwargs.pop('disk_number')
        return create_element(
            'disk', type='file', device='cdrom', attribute_dict={
                'children': [
                    create_element('driver', name='qemu', type='raw'),
                    create_element('source', file=self.data['attributes']['path']),
                    create_element('target', dev=f'sd{disk_from_number(disk_number)}', bus='sata'),
                    create_element('boot', order=str(kwargs.pop('boot_number'))),
                ]
            }
        )
