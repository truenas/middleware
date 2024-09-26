import asyncio

from middlewared.plugins.docker.state_utils import Status

from .base import SimpleService


class DockerService(SimpleService):
    name = 'docker'
    etc = ['docker']
    systemd_unit = 'docker'

    async def mount_umount_ix_apps(self, mount):
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

    async def before_start(self):
        await self.middleware.call('docker.state.set_status', Status.INITIALIZING.value)
        await self.middleware.call('docker.state.before_start_check')
        await self.mount_umount_ix_apps(True)
        await self.middleware.call('catalog.sync')
        for key, value in (
            ('vm.panic_on_oom', 0),
            ('vm.overcommit_memory', 1),
        ):
            await self.middleware.call('sysctl.set_value', key, value)

    async def start(self):
        try:
            await super().start()
            timeout = 120  # We have this at 120 because HDDs are notorious and docker can take more time there
            # First time when docker is started, it takes a bit more time to initialise itself properly
            # and we need to have sleep here so that after start is called post_start is not dismissed
            while timeout > 0:
                if not await self.middleware.call('service.started', 'docker'):
                    await asyncio.sleep(2)
                    timeout -= 2
                else:
                    break
        finally:
            asyncio.get_event_loop().call_later(
                2,
                lambda: self.middleware.create_task(self.middleware.call('docker.state.after_start_check')),
            )

    async def stop(self):
        await super().stop()
        await self._systemd_unit('docker.socket', 'stop')

    async def after_start(self):
        await self.middleware.call('docker.state.set_status', Status.RUNNING.value)
        self.middleware.create_task(self.middleware.call('docker.events.setup'))
        await self.middleware.call('catalog.sync')
        if (await self.middleware.call('docker.config'))['enable_image_updates']:
            self.middleware.create_task(self.middleware.call('app.image.op.check_update'))

    async def before_stop(self):
        await self.middleware.call('docker.state.set_status', Status.STOPPING.value)

    async def after_stop(self):
        await self.mount_umount_ix_apps(False)
        await self.middleware.call('docker.state.set_status', Status.STOPPED.value)
        await self.middleware.call('catalog.sync')
