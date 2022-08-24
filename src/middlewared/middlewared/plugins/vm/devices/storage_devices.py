import errno
import os

from middlewared.plugins.zfs_.utils import zvol_name_to_path
from middlewared.schema import Bool, Dict, Int, Str
from middlewared.validators import Match

from .device import Device
from .utils import create_element, disk_from_number


IOTYPE_CHOICES = ['NATIVE', 'THREADS', 'IO_URING']


class StorageDevice(Device):

    TYPE = NotImplemented

    def identity(self):
        return self.data['attributes']['path']

    def is_available(self):
        return os.path.exists(self.identity())

    def xml_linux(self, *args, **kwargs):
        disk_number = kwargs.pop('disk_number')
        virtio = self.data['attributes']['type'] == 'VIRTIO'
        logical_sectorsize = self.data['attributes']['logical_sectorsize']
        physical_sectorsize = self.data['attributes']['physical_sectorsize']
        iotype = self.data['attributes']['iotype']

        return create_element(
            'disk', type=self.TYPE, device='disk', attribute_dict={
                'children': [
                    create_element('driver', name='qemu', type='raw', cache='none', io=iotype.lower()),
                    self.create_source_element(),
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

    def create_source_element(self):
        raise NotImplementedError

    def _validate(self, device, verrors, old=None, vm_instance=None, update=True):
        if not self.middleware.call_sync('vm.device.disk_uniqueness_integrity_check', device, vm_instance):
            verrors.add(
                'attributes.path',
                f'{vm_instance["name"]} has "{self.identity()}" already configured'
            )

        if device['attributes'].get('physical_sectorsize') and not device['attributes'].get('logical_sectorsize'):
            verrors.add(
                'attributes.logical_sectorsize',
                'This field must be provided when physical_sectorsize is specified.'
            )


class RAW(StorageDevice):

    TYPE = 'file'

    schema = Dict(
        'attributes',
        Str('path', required=True, validators=[Match(
            r'^[^{}]*$', explanation='Path should not contain "{", "}" characters'
        )], empty=False),
        Str('type', enum=['AHCI', 'VIRTIO'], default='AHCI'),
        Bool('exists'),
        Bool('boot', default=False),
        Int('size', default=None, null=True),
        Int('logical_sectorsize', enum=[None, 512, 4096], default=None, null=True),
        Int('physical_sectorsize', enum=[None, 512, 4096], default=None, null=True),
        Str('iotype', enum=IOTYPE_CHOICES, default='THREADS'),
    )

    def create_source_element(self):
        return create_element('source', file=self.data['attributes']['path'])

    def _validate(self, device, verrors, old=None, vm_instance=None, update=True):
        path = device['attributes']['path']
        exists = device['attributes'].get('exists', True)
        if exists and not os.path.exists(path):
            verrors.add('attributes.path', 'Path must exist when "exists" is set.')
        elif not exists:
            if os.path.exists(path):
                verrors.add('attributes.path', 'Path must not exist when "exists" is unset.')
            elif not device['attributes'].get('size'):
                verrors.add('attributes.size', 'Please provide a valid size for the raw file.')

        if (
            old and old['attributes'].get('size') != device['attributes'].get('size') and
            not device['attributes'].get('size')
        ):
            verrors.add('attributes.size', 'Please provide a valid size for the raw file.')

        self.middleware.call_sync('vm.device.validate_path_field', verrors, 'attributes.path', path)

        super()._validate(device, verrors, old, vm_instance, update)


class DISK(StorageDevice):

    TYPE = 'block'

    schema = Dict(
        'attributes',
        Str('path'),
        Str('type', enum=['AHCI', 'VIRTIO'], default='AHCI'),
        Bool('create_zvol'),
        Str('zvol_name'),
        Int('zvol_volsize'),
        Int('logical_sectorsize', enum=[None, 512, 4096], default=None, null=True),
        Int('physical_sectorsize', enum=[None, 512, 4096], default=None, null=True),
        Str('iotype', enum=IOTYPE_CHOICES, default='THREADS'),
    )

    def create_source_element(self):
        return create_element('source', dev=self.data['attributes']['path'])

    def _validate(self, device, verrors, old=None, vm_instance=None, update=True):
        create_zvol = device['attributes'].get('create_zvol')
        path = device['attributes'].get('path')

        if create_zvol:
            for attr in ('zvol_name', 'zvol_volsize'):
                if not device['attributes'].get(attr):
                    verrors.add(f'attributes.{attr}', 'This field is required.')
            if device['attributes'].get('path'):
                verrors.add('attributes.path', 'Must not be specified when creating zvol')

            verrors.check()

            # Add normalized path for the zvol
            device['attributes']['path'] = zvol_name_to_path(device['attributes']['zvol_name'])

            if zvol := self.middleware.call_sync(
                'pool.dataset.query', [['id', '=', device['attributes']['zvol_name']]]
            ):
                verrors.add('attributes.zvol_name', f'{zvol[0]["id"]!r} already exists.')

            parentzvol = device['attributes']['zvol_name'].rsplit('/', 1)[0]
            if parentzvol and not self.middleware.call_sync('pool.dataset.query', [('id', '=', parentzvol)]):
                verrors.add(
                    'attributes.zvol_name',
                    f'Parent dataset {parentzvol} does not exist.', errno.ENOENT
                )
        else:
            for attr in filter(lambda k: device['attributes'].get(k), ('zvol_name', 'zvol_volsize')):
                verrors.add(f'attributes.{attr}', 'This field should not be specified when "create_zvol" is unset.')

            if not path:
                verrors.add('attributes.path', 'Disk path is required.')
            elif path and not os.path.exists(path):
                verrors.add('attributes.path', f'Disk path {path} does not exist.', errno.ENOENT)

        super()._validate(device, verrors, old, vm_instance, update)
