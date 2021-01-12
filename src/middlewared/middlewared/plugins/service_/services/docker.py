from middlewared.plugins.service_.services.base import SimpleService


class DockerService(SimpleService):
    name = 'docker'
    etc = ['docker']
    systemd_unit = 'docker'

    async def _start_linux(self):
        # https://jira.ixsystems.com/browse/NAS-108883 we see that docker did not start right away
        # and takes 17 seconds to initialize.
        await self._unit_action('Start', timeout=30)
