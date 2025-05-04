import errno
import os

from middlewared.api import api_method
from middlewared.api.current import VirtInstanceStorageRenameArgs, VirtInstanceStorageRenameResult
from middlewared.plugins.zfs_.utils import zvol_path_to_name
from middlewared.service import CallError, private, Service


class VirtInstanceStorageService(Service):

    class Config:
        namespace = 'virt.instance.storage'
        cli_namespace = 'virt.instance.storage'

    @private
    async def virt_path(self, path):
        """
        Returns a boolean which is set when path provided is being used by virt.
        """
        # We are only factoring in zvols and not host path mounts because that can
        # be used by other attachments as well
        global_config = await self.middleware.call('virt.global.config')
        instance_paths = {
            zvol_path_to_name(p)
            for p in set((await self.middleware.call('virt.instance.get_all_disk_sources')).keys())
            if p.startswith('/dev/zvol/')
        }
        return any(
            p == path or path.startswith(f'{p}/')
            for p in instance_paths | {os.path.join(p, '.ix-virt') for p in global_config['storage_pools']}
        )

    @api_method(VirtInstanceStorageRenameArgs, VirtInstanceStorageRenameResult, roles=['VIRT_INSTANCE_WRITE'])
    async def rename(self, data):
        """
        Rename a zfs dataset/snapshot used by virt
        """
        zfs_resource = data['name']
        if '@' in zfs_resource:
            ds_name = zfs_resource.split('@')[0]
            namespace = 'zfs.snapshot'
            args = data['new_name']
        else:
            ds_name = zfs_resource
            namespace = 'zfs.dataset'
            args = {'new_name': data['new_name']}

        # Let's make sure zfs resource actually exists
        await self.middleware.call(f'{namespace}.get_instance', zfs_resource)

        # Check if the dataset is being used by virt
        if await self.virt_path(ds_name) is False:
            raise CallError('Only zfs resources used by virt can be renamed', errno.EINVAL)

        await self.middleware.call(f'{namespace}.rename', zfs_resource, args)
        return True
