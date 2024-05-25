import asyncio

from .base import SimpleService


class DockerService(SimpleService):
    name = 'docker'
    etc = ['docker']
    systemd_unit = 'docker'

    async def before_start(self):
        # TODO: Add status updates here and start checks
        # FIXME: We should have alerts as well in case of failure to validate
        await self.middleware.call('docker.setup.validate_fs')
        for key, value in (
            ('vm.panic_on_oom', 0),
            ('vm.overcommit_memory', 1),
        ):
            await self.middleware.call('sysctl.set_value', key, value)

    async def start(self):
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

    async def before_stop(self):
        # TODO: Add status updates here and any other custom stuff which might need to be done
        pass
