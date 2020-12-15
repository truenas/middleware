import os

from middlewared.schema import Bool, Dict, Int, Str

from .device import Device
from .utils import create_element, disk_from_number


class StorageDevice(Device):

    def identity(self):
        return self.data['attributes']['path']

    def is_available(self):
        return os.path.exists(self.identity())

    def xml_linux(self, *args, **kwargs):
        disk_number = kwargs.pop('disk_number')
        virtio = self.data['attributes']['type'] == 'VIRTIO'
        logical_sectorsize = self.data['attributes']['logical_sectorsize']
        physical_sectorsize = self.data['attributes']['physical_sectorsize']

        return create_element(
            'disk', type='block', device='disk', attribute_dict={
                'children': [
                    create_element('driver', name='qemu', type='raw', cache='none'),
                    create_element('source', dev=self.data['attributes']['path']),
                    create_element(
                        'target', bus='sata' if not virtio else 'virtio',
                        dev=f'{"vd" if virtio else "sd"}{disk_from_number(disk_number)}'
                    ),
                    create_element('boot', order=str(kwargs.pop('boot_number'))),
                    *([] if not logical_sectorsize else [create_element(
                        'blockio', logical_block_size=str(logical_sectorsize), **({} if not physical_sectorsize else {
                            'physical_block_size': str(physical_sectorsize)
                        })
                    )]),
                ]
            }
        )

    def xml_freebsd(self, *args, **kwargs):
        child_element = kwargs.pop('child_element')
        virtio = self.data['attributes']['type'] == 'VIRTIO'
        logical_sectorsize = self.data['attributes']['logical_sectorsize']
        physical_sectorsize = self.data['attributes']['physical_sectorsize']

        return create_element(
            'disk', type='file', device='disk', attribute_dict={
                'children': [
                    create_element('source', file=self.data['attributes']['path']),
                    create_element(
                        'target', bus='sata' if not virtio else 'virtio',
                        dev=f'{"hdc" if not virtio else "vdb"}{self.data["id"]}'
                    ),
                    child_element,
                    *([] if not logical_sectorsize else [create_element(
                        'blockio', logical_block_size=str(logical_sectorsize), **({} if not physical_sectorsize else {
                            'physical_block_size': str(physical_sectorsize)
                        })
                    )]),
                ]
            }
        )


class RAW(StorageDevice):

    schema = Dict(
        'attributes',
        Str('path', required=True),
        Str('type', enum=['AHCI', 'VIRTIO'], default='AHCI'),
        Bool('exists'),
        Bool('boot', default=False),
        Int('size', default=None, null=True),
        Int('logical_sectorsize', enum=[None, 512, 4096], default=None, null=True),
        Int('physical_sectorsize', enum=[None, 512, 4096], default=None, null=True),
    )


class DISK(StorageDevice):

    schema = Dict(
        'attributes',
        Str('path'),
        Str('type', enum=['AHCI', 'VIRTIO'], default='AHCI'),
        Bool('create_zvol'),
        Str('zvol_name'),
        Int('zvol_volsize'),
        Int('logical_sectorsize', enum=[None, 512, 4096], default=None, null=True),
        Int('physical_sectorsize', enum=[None, 512, 4096], default=None, null=True),
    )
