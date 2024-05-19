from middlewared.schema import accepts, Dict, Int, Patch, Str
from middlewared.service import ConfigService, job


class DockerService(ConfigService):

    class Config:
        datastore = 'services.docker'
        cli_namespace = 'app.docker'
        role_prefix = 'DOCKER'

    ENTRY = Dict(
        'docker_entry',
        Int('id', required=True),
        Str('name', required=True),
        update=True,
    )

    @accepts(
        Patch(
            'docker_entry', 'docker_update',
            ('rm', {'name': 'id'}),
            ('rm', {'name': 'dataset'}),
            ('attr', {'update': True}),
        )
    )
    @job(lock='docker_update')
    async def do_update(self, job, data):
        """
        Update Docker service configuration.
        """
        old_config = await self.config()
        old_config.pop('dataset')
        config = old_config.copy()
        config.update(data)

        if len(set(old_config.items()) ^ set(config.items())) > 0:
            await self.middleware.call('datastore.update', self._config.datastore, old_config['id'], config)

        return await self.config()
