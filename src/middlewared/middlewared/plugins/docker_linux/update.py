import middlewared.sqlalchemy as sa

from middlewared.schema import Bool, Dict
from middlewared.service import accepts, ConfigService


class ContainerModel(sa.Model):
    __tablename__ = 'services_container'

    id = sa.Column(sa.Integer(), primary_key=True)
    enable_image_updates = sa.Column(sa.Boolean(), default=True)


class ContainerService(ConfigService):

    class Config:
        datastore = 'services.kubernetes'

    @accepts(
        Dict(
            'container_update',
            Bool('enable_image_updates'),
            update=True,
        )
    )
    async def do_update(self, data):
        old_config = await self.config()
        config = old_config.copy()
        config.update(data)

        await self.middleware.call('datastore.update', self._config.datastore, old_config['id'], config)

        return await self.config()
