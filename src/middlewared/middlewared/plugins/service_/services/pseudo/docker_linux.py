from middlewared.plugins.service_.services.base import SimpleService


class DockerService(SimpleService):
    name = 'docker'
    etc = ['docker']
    systemd_unit = 'docker'

    async def _start_linux(self):
        await self._unit_action('Start')

    async def _stop_linux(self):
        await self._unit_action('Stop')
