import middlewared.sqlalchemy as sa

from middlewared.api import api_method
from middlewared.api.current import (
    ContainerConfigEntry, ContainerConfigUpdateArgs, ContainerConfigUpdateResult
)
from middlewared.service import ConfigService


class ContainerConfigModel(sa.Model):
    __tablename__ = 'container_config'

    id = sa.Column(sa.Integer(), primary_key=True)
    image_dataset = sa.Column(sa.Text(), nullable=True, default=None)


class ContainerConfigService(ConfigService):

    class Config:
        cli_namespace = 'service.container.config'
        datastore = 'container_config'
        namespace = 'container.config'
        role_prefix = 'CONTAINER_CONFIG'
        entry = ContainerConfigEntry

    @api_method(ContainerConfigUpdateArgs, ContainerConfigUpdateResult)
    async def do_update(self, data):
        """
        Update container config.
        """
        old_config = await self.config()
        config = old_config.copy()
        config.update(data)

        await self.middleware.call('datastore.update', self._config.datastore, old_config['id'], config)

        return await self.config()
