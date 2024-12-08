import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import TNCEntry, TNCUpdateArgs, TNCUpdateResult
from middlewared.service import ConfigService

from .status_utils import Status


class TrueNASConnectModel(sa.Model):
    __tablename__ = 'truenas_connect'

    id = sa.Column(sa.Integer(), primary_key=True)
    enabled = sa.Column(sa.Boolean(), default=False, nullable=False)
    jwt_token = sa.Column(sa.EncryptedText(), default=None, nullable=True)
    registration_details = sa.Column(sa.JSON(dict), nullable=False)
    ips = sa.Column(sa.JSON(list), nullable=False)
    status = sa.Column(sa.String(255), default=Status.DISABLED.name, nullable=False)


class TrueNASConnectService(ConfigService):

    # TODO: Add roles
    class Config:
        datastore = 'truenas_connect'
        cli_private = True
        namespace = 'tn_connect'
        entry = TNCEntry

    @api_method(TNCUpdateArgs, TNCUpdateResult)
    async def do_update(self, data):
        """
        Update TrueNAS Connect configuration.
        """
        config = await self.config()
        config.update(data)
        # TODO: Handle the case where user imports same db in a different system
        await self.middleware.call(
            'datastore.update', self._config.datastore, config['id'], {'enabled': config['enabled']}
        )
        return await self.config()
