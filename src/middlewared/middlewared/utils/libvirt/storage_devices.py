import errno
import os

from middlewared.api.current import VMDiskDevice, VMRAWDevice
from middlewared.plugins.zfs.utils import has_internal_path
from middlewared.plugins.zfs_.utils import zvol_name_to_path, zvol_path_to_name
from middlewared.plugins.zfs_.validation_utils import check_zvol_in_boot_pool_using_path
from middlewared.service_exception import ValidationErrors
from middlewared.utils.crypto import generate_string

from .delegate import DeviceDelegate


IOTYPE_CHOICES = ['NATIVE', 'THREADS', 'IO_URING']


class StorageDelegate(DeviceDelegate):

    def validate_middleware(
        self,
        device: dict,
        verrors: ValidationErrors,
        old: dict | None = None,
        vm_instance: dict | None = None,
        update: bool = True,
    ) -> None:
        identity = device['attributes'].get('path') or zvol_name_to_path(device['attributes']['zvol_name'])
        if not self.middleware.call_sync('vm.device.disk_uniqueness_integrity_check', device, vm_instance):
            verrors.add(
                'attributes.path',
                f'{vm_instance["name"]} has "{identity}" already configured'
            )

        if update is False:
            device['attributes']['serial'] = generate_string(8)
        elif not device['attributes'].get('serial'):
            # As this is a json field, ensure that some consumer does not remove this value, in that case
            # we preserve the original value
            device['attributes']['serial'] = old['attributes']['serial']
        elif device['attributes']['serial'] != old['attributes']['serial']:
            verrors.add('attributes.serial', 'This field is read-only.')


class RAWDelegate(StorageDelegate):

    @property
    def schema_model(self):
        return VMRAWDevice

    def validate_middleware(
        self,
        device: dict,
        verrors: ValidationErrors,
        old: dict | None = None,
        vm_instance: dict | None = None,
        update: bool = True,
    ) -> None:
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

        super().validate_middleware(device, verrors, old, vm_instance, update)


class DiskDelegate(StorageDelegate):

    @property
    def schema_model(self):
        return VMDiskDevice

    def validate_middleware(
        self,
        device: dict,
        verrors: ValidationErrors,
        old: dict | None = None,
        vm_instance: dict | None = None,
        update: bool = True,
    ) -> None:
        create_zvol = device['attributes'].get('create_zvol')
        path = device['attributes'].get('path')

        if create_zvol:
            for attr in ('zvol_name', 'zvol_volsize'):
                if not device['attributes'].get(attr):
                    verrors.add(f'attributes.{attr}', 'This field is required.')
            if device['attributes'].get('path'):
                verrors.add('attributes.path', 'The "path" attribute must not be specified when creating a zvol.')

            if has_internal_path(device['attributes']['zvol_name']):
                # before doing anything, let's make sure the zvol
                # being created isn't within an internal path
                verrors.add(
                    'attributes.zvol_name',
                    f'Invalid location specified for {device["attributes"]["zvol_name"]!r}.'
                )

            verrors.check()

            # Add normalized path for the zvol
            device['attributes']['path'] = zvol_name_to_path(device['attributes']['zvol_name'])

            zvol = self.middleware.call_sync(
                'zfs.resource.query_impl',
                {'paths': [device['attributes']['zvol_name']], 'properties': None}
            )
            if zvol:
                verrors.add('attributes.zvol_name', f'{zvol[0]["name"]!r} already exists.')
            else:
                # check for parent's existence so we can give a validation error
                # message that is more intuitive for end-user
                parentzvol = device['attributes']['zvol_name'].rsplit('/', 1)[0]
                if parentzvol and not self.middleware.call_sync(
                        'zfs.resource.query_impl', {'paths': [parentzvol], 'properties': None}
                ):
                    verrors.add(
                        'attributes.zvol_name',
                        f'Parent {parentzvol!r} does not exist.', errno.ENOENT
                    )
        else:
            for attr in filter(lambda k: device['attributes'].get(k), ('zvol_name', 'zvol_volsize')):
                verrors.add(f'attributes.{attr}', 'This field should not be specified when "create_zvol" is unset.')

            if not path:
                verrors.add('attributes.path', 'Disk path is required.')
            elif not path.startswith('/dev/zvol/'):
                verrors.add('attributes.path', 'Disk path must start with "/dev/zvol/".')
            elif check_zvol_in_boot_pool_using_path(path):
                verrors.add('attributes.path', 'Disk residing in boot pool cannot be consumed and is not supported.')
            else:
                zvol_name = zvol_path_to_name(path)
                zvol = self.middleware.call_sync(
                    'zfs.resource.query_impl', {'paths': [zvol_name], 'properties': None}
                )
                if not zvol:
                    verrors.add(
                        'attributes.path',
                        f'Zvol ({zvol_name}) path ({path}) does not exist.',
                        errno.ENOENT
                    )
                elif zvol[0]['type'] != 'VOLUME':
                    verrors.add('attributes.path', f'Path {path!r} ({zvol_name}) is not a volume.')
                elif has_internal_path(zvol_name):
                    verrors.add(
                        'attributes.path',
                        'Disk resides in an invalid location and is not supported.'
                    )

        super().validate_middleware(device, verrors, old, vm_instance, update)
