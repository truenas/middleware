import errno

from middlewared.service import CallError, Service

from .state_utils import docker_dataset_custom_props, IX_APPS_MOUNT_PATH, Status


class DockerFilesystemManageService(Service):

    class Config:
        namespace = 'docker.fs_manage'
        private = True

    async def common_func(self, mount):
        if docker_ds := (await self.middleware.call('docker.config'))['dataset']:
            try:
                if mount:
                    # Check if ix-apps dataset mount point needs updating
                    await self.ensure_ix_apps_mount_point(docker_ds)
                    await self.middleware.call('zfs.dataset.mount', docker_ds, {'recursive': True, 'force_mount': True})
                else:
                    await self.middleware.call('zfs.dataset.umount', docker_ds, {'force': True})
                return await self.middleware.call('catalog.sync')
            except Exception as e:
                await self.middleware.call(
                    'docker.state.set_status', Status.FAILED.value,
                    f'Failed to {"mount" if mount else "umount"} {docker_ds!r}: {e}',
                )
                raise

    async def mount(self):
        return await self.common_func(True)

    async def umount(self):
        return await self.common_func(False)

    async def ensure_ix_apps_mount_point(self, docker_ds):
        """
        Ensure ix-apps dataset is mounted at /mnt/.ix-apps and update it accordingly.

        This is helpful in the event when user rolled back to a previous version of TN
        where docker apps were not supported, what happens here is that the mountpoint of
        ix-apps dataset is reset and it gets mounted under root dataset. Now when he comes back
        to newer TN version, we need to update the mount point of ix-apps dataset so it gets reflected
        properly.
        """
        dataset_info = await self.middleware.call(
            'zfs.dataset.query',
            [['name', '=', docker_ds]], {
                'extra': {'properties': ['mountpoint'], 'retrieve_children': False}
            }
        )
        if not dataset_info:
            return

        current_mount = dataset_info[0]['properties'].get('mountpoint', {}).get('value')
        # If the mount point is not at the expected location, fix it
        if current_mount != IX_APPS_MOUNT_PATH:
            # Update the main ix-apps dataset mount point
            await self.middleware.call(
                'zfs.dataset.update',
                docker_ds, {
                    'properties': {
                        'mountpoint': {
                            'value': docker_dataset_custom_props(docker_ds.split('/')[-1])['mountpoint']
                        },
                    },
                }
            )

    async def ix_apps_is_mounted(self, dataset_to_check=None):
        """
        This will tell us if some dataset is mounted on /mnt/.ix-apps or not.
        """
        try:
            fs_details = await self.middleware.call('filesystem.statfs', IX_APPS_MOUNT_PATH)
        except CallError as e:
            if e.errno == errno.ENOENT:
                return False
            raise

        if fs_details['source'].startswith('boot-pool/'):
            return False

        if dataset_to_check:
            return fs_details['source'] == dataset_to_check

        return True
