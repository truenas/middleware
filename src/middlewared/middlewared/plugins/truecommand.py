import subprocess

import middlewared.sqlalchemy as sa

from middlewared.schema import Bool, Dict, Str
from middlewared.service import accepts, CallError, private, ConfigService, ValidationErrors
from middlewared.utils import Popen
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
            'truecommand_update',
            Bool('enabled'),
            Str('api_key', null=True, validators=[Range(min=16, max=16)]),
        )
    )
    async def do_update(self, data):
        internal_config = await self.middleware.call('datastore.config', self._config.datastore)
        old = await self.config()
        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()
        if new['enabled'] and not new['api_key']:
            verrors.add(
                'truecommand_update.api_key',
                'API Key must be provided when Truecommand service is enabled.'
            )

        verrors.check()

        if new['enabled'] and (not internal_config['wg_public_key'] or not internal_config['wg_private_key']):
            new.update(**(await self.generate_wg_keys()))

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            old['id'],
            new
        )

        if new['enabled']:
            # We are going to perform following steps when tc service is enabled
            # 1) Send a post request to portal to register new api key ( only if it differs from the old one )
            # 2) Get status of existing api key ( if we already had it and it was maybe just disabled )
            if old['api_key'] != new['api_key']:
                pass

        return await self.config()

    @private
    async def generate_wg_keys(self):
        cp = await Popen(['wg', 'genkey'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        private_key, stderr = await cp.communicate()
        if cp.returncode:
            raise CallError(
                f'Failed to generate key for wireguard with exit code ({cp.returncode}): {stderr.decode()}'
            )

        cp = await Popen(
            ['wg', 'pubkey'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        public_key, stderr = await cp.communicate(input=private_key)
        if cp.returncode:
            raise CallError(
                f'Failed to generate public key for wireguard with exit code ({cp.returncode}): {stderr.decode()}'
            )

        return {'wg_public_key': public_key.decode().strip(), 'wg_private_key': private_key.decode().strip()}
