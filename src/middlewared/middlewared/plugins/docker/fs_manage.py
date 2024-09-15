from middlewared.service import Service

from .state_utils import Status


class DockerFilesystemManageService(Service):

    class Config:
        namespace = 'docker.fs_manage'
        private = True

    async def common_func(self, mount):
        if docker_ds := (await self.middleware.call('docker.config'))['dataset']:
            try:
                if mount:
                    await self.middleware.call('zfs.dataset.mount', docker_ds, {'recursive': True, 'force_mount': True})
                else:
                    await self.middleware.call('zfs.dataset.umount', docker_ds, {'force': True})
                await self.middleware.call('catalog.sync')
            except Exception as e:
                await self.middleware.call(
                    'docker.state.set_status', Status.FAILED.value,
                    f'Failed to {"mount" if mount else "umount"} {docker_ds!r}: {e}',
                )
                raise

    async def mount(self):
        await self.common_func(True)

    async def umount(self):
        await self.common_func(False)
