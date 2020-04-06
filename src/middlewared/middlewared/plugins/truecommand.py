from middlewared.schema import Bool, Dict, Str
from middlewared.service import accepts, CallError, private, ConfigService, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.validators import Range


class TrueCommandModel(sa.Model):
    __tablename__ = 'system_truecommand'

    id = sa.Column(sa.Integer(), primary_key=True)
    api_key = sa.Column(sa.String(128), default=None, nullable=True)
    api_key_state = sa.Column(sa.String(128), default='DISABLED', nullable=True)
    wg_public_key = sa.Column(sa.String(255), default=None, nullable=True)
    wg_private_key = sa.Column(sa.String(255), default=None, nullable=True)
    wg_address = sa.Column(sa.String(255), default=None, nullable=True)
    tc_public_key = sa.Column(sa.String(255), default=None, nullable=True)
    endpoint = sa.Column(sa.String(255), default=None, nullable=True)
    remote_address = sa.Column(sa.String(255), default=None, nullable=True)
    enabled = sa.Column(sa.Boolean(), default=False)


class TrueCommandService(ConfigService):

    POLLING_GAP_MINUTES = 5

    class Config:
        service = 'truecommand'
        datastore = 'services.truecommand'
        datastore_extend = 'truecommand.tc_extend'

    @private
    async def tc_extend(self, config):
        for key in ('wg_public_key', 'wg_private_key', 'tc_public_key', 'endpoint'):
            config.pop(key)
        return config

    @accepts(
        Dict(
            'truecommand_update_config',
            Bool('enabled'),
            Str('api_key', null=True, validators=[Range(min=16, max=16)]),
        )
    )
    async def do_update(self, data):
        old = await self.config()
        new = old.copy()
        new.update(data)

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            old['id'],
            new
        )

        return await self.config()
