import asyncio

from middlewared.plugins.docker.state_utils import Status

from .base import SimpleService


class DockerService(SimpleService):
    name = 'docker'
    etc = ['docker']
    systemd_unit = 'docker'

    async def before_start(self):
        await self.middleware.call('docker.state.set_status', Status.INITIALIZING.value)
        await self.middleware.call('docker.state.before_start_check')
        for key, value in (
            ('vm.panic_on_oom', 0),
            ('vm.overcommit_memory', 1),
        ):
            await self.middleware.call('sysctl.set_value', key, value)

    async def start(self):
        # FIXME: This probably needs to be blacklisted in failover service as well
        try:
            await super().start()
            timeout = 40
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

    async def after_start(self):
        await self.middleware.call('docker.state.set_status', Status.RUNNING.value)

    async def before_stop(self):
        await self.middleware.call('docker.state.set_status', Status.STOPPING.value)

    async def after_stop(self):
        await self.middleware.call('docker.state.set_status', Status.STOPPED.value)
