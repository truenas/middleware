import os

from middlewared.plugins.boot import BOOT_POOL_NAME
from middlewared.service import CallError, ValidationErrors
from middlewared.utils.path import check_path_resides_within_volume_sync
from middlewared.utils.zfs import query_imported_fast_impl

from .delegate import DeviceDelegate
from .utils import LIBVIRT_USER, disk_uniqueness_integrity_check


class CDROMDelegate(DeviceDelegate):

    def validate_middleware(
        self,
        device: dict,
        verrors: ValidationErrors,
        old: dict | None = None,
        instance: dict | None = None,
        update: bool = True,
    ) -> None:
        path = device['attributes']['path']
        check_path_resides_within_volume_sync(
            verrors, 'attributes.path', path, [
                i['name'] for i in query_imported_fast_impl().values() if i['name'] != BOOT_POOL_NAME
            ]
        )
        if not disk_uniqueness_integrity_check(device, instance):
            verrors.add(
                'attributes.path',
                f'{instance["name"]} has {path!r} already configured'
            )

        if verrors:
            return

        if self.middleware.call_sync('filesystem.statfs', path)['dest'].count('/') < 3:
            verrors.add('attributes.path', 'The path must be a dataset or a directory within a dataset.')
            return

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
