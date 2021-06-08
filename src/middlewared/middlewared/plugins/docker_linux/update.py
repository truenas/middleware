import middlewared.sqlalchemy as sa

from middlewared.schema import Bool, Dict, Int
from middlewared.service import ConfigService


class ContainerModel(sa.Model):
    __tablename__ = 'services_container'

    id = sa.Column(sa.Integer(), primary_key=True)
    enable_image_updates = sa.Column(sa.Boolean(), default=True)


class ContainerService(ConfigService):

    class Config:
        datastore = 'services.container'
        cli_namespace = 'app.container.config'

    ENTRY = Dict(
        'container_entry',
        Bool('enable_image_updates'),
        Int('id'),
    )

    async def do_update(self, data):
        """
        When `enable_image_updates` is set, system will check if existing container images need to be updated. System
        will basically check if we have an updated image hash available for the same tag available and if we do,
        user is alerted to update the image.
        A use case for unsetting this variable can be rate limits for docker registries, as each time we check if a
        single image needs update, we consume the rate limit and eventually it can hinder operations if the number
        of images to be checked is a lot.
        """
        old_config = await self.config()
        config = old_config.copy()
        config.update(data)

        await self.middleware.call('datastore.update', self._config.datastore, old_config['id'], config)

        return await self.config()
