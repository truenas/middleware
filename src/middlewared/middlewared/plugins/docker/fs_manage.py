import errno

from middlewared.service import CallError, Service
from middlewared.plugins.pool_.utils import UpdateImplArgs
from middlewared.plugins.zfs.mount_unmount_impl import MountArgs, UnmountArgs

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
                    await self.middleware.call(
                        'zfs.resource.mount',
                        MountArgs(filesystem=docker_ds, force=True, recursive=True)
                    )
                else:
                    await self.middleware.call(
                        'zfs.resource.unmount',
                        UnmountArgs(filesystem=docker_ds, force=True, recursive=True)
                    )
                try:
                    return await self.middleware.call('catalog.sync')
                except CallError as e:
                    if e.errno != errno.EBUSY:
                        raise
            except Exception as e:
                await self.middleware.call(
                    'docker.state.set_status', Status.FAILED.value,
                    f'Failed to {"mount" if mount else "umount"} {docker_ds!r}: {e}',
                )
                raise

    async def mount(self):
        return await self.common_func(True)

    async def umount(self):
        # Wait for any running catalog.sync job before unmounting.
        # A running sync determines its target path at start - if it started
        # while mounted, it writes to /mnt/.ix-apps/truenas_catalog. Unmounting
        # while sync is active would cause writes to an invalid path.
        for job in await self.middleware.call(
            'core.get_jobs', [['method', '=', 'catalog.sync'], ['state', '=', 'RUNNING']]
        ):
            await (await self.middleware.call('core.job_wait', job['id'])).wait()

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
        ds = await self.middleware.call(
            'zfs.resource.query_impl',
            {'paths': [docker_ds], 'properties': ['mountpoint']}
        )
        if not ds:
            return

        # If the mount point is not at the expected location, fix it
        if ds[0]['properties']['mountpoint']['value'] != IX_APPS_MOUNT_PATH:
            mp = docker_dataset_custom_props(docker_ds.split('/')[-1])['mountpoint']
            await self.middleware.call(
                'pool.dataset.update_impl',
                UpdateImplArgs(name=docker_ds, zprops={'mountpoint': mp})
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
