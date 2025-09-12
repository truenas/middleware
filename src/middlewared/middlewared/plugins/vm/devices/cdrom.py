import os

from middlewared.api.current import VMCDROMDevice
from middlewared.plugins.boot import BOOT_POOL_NAME
from middlewared.schema import Dict
from middlewared.service import CallError
from middlewared.utils.zfs import query_imported_fast_impl
from middlewared.utils.path import check_path_resides_within_volume_sync

from .device import Device
from .utils import create_element, disk_from_number, LIBVIRT_USER


class CDROM(Device):

    schema = Dict(
        'attributes',
    )
    schema_model = VMCDROMDevice

    def identity(self):
        return self.data['attributes']['path']

    def is_available(self):
        return os.path.exists(self.identity())

    def xml(self, *args, **kwargs):
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

    def _validate(self, device, verrors, old=None, vm_instance=None, update=True):
        path = device['attributes']['path']
        check_path_resides_within_volume_sync(
            verrors, 'attributes.path', path, [
                i['name'] for i in query_imported_fast_impl().values() if i['name'] != BOOT_POOL_NAME
            ]
        )
        if not self.middleware.call_sync('vm.device.disk_uniqueness_integrity_check', device, vm_instance):
            verrors.add(
                'attributes.path',
                f'{vm_instance["name"]} has "{self.identity()}" already configured'
            )

        if not verrors:
            # We would like to check now if libvirt will actually be able to read the iso file
            # How this works is that if libvirt user is not able to read the file, libvirt automatically changes
            # ownership of the iso file to the libvirt user so that it is able to read however there are cases where
            # even this can fail with perms like 000 or maybe parent path(s) not allowing access.
            # To mitigate this, we can do the following:
            # 1) See if owner of the file is libvirt user
            # 2) If it's not libvirt user:
            # a) Check if libvirt user can access the file
            # b) Change ownership of the file to libvirt user as libvirt would eventually do
            # 3) Check if libvirt user can access the file
            libvirt_user = self.middleware.call_sync('user.get_user_obj', {"username": LIBVIRT_USER})
            current_owner = os.stat(path)
            is_valid = False
            if current_owner.st_uid != libvirt_user['pw_uid']:
                if self.middleware.call_sync('filesystem.can_access_as_user', LIBVIRT_USER, path, {'read': True}):
                    is_valid = True
                else:
                    os.chown(path, libvirt_user['pw_uid'], libvirt_user['pw_gid'])
            if not is_valid:
                try:
                    self.middleware.call_sync(
                        'filesystem.check_path_execute', path, 'USER', libvirt_user['pw_uid'], False
                    )
                except CallError as e:
                    verrors.add('attributes.path', e.errmsg)

                if not self.middleware.call_sync(
                    'filesystem.can_access_as_user', LIBVIRT_USER, path, {'read': True}
                ):
                    verrors.add(
                        'attributes.path',
                        f'{LIBVIRT_USER!r} user cannot read from {path!r} path. Please ensure correct '
                        'permissions are specified.'
                    )
                # Now that we know libvirt user would not be able to read the file in any case,
                # let's rollback the chown change we did
                os.chown(path, current_owner.st_uid, current_owner.st_gid)
