import base64
import pyotp

import middlewared.sqlalchemy as sa

from middlewared.schema import accepts, Bool, Dict, Int, Patch
from middlewared.service import ConfigService, private
from middlewared.validators import Range


class TwoFactoryUserAuthModel(sa.Model):
    __tablename__ = 'account_twofactor_user_auth'

    id = sa.Column(sa.Integer(), primary_key=True)
    secret = sa.Column(sa.EncryptedText(), nullable=True, default=None)
    user_id = sa.Column(sa.ForeignKey('account_bsdusers.id', ondelete='CASCADE'), index=True, nullable=True)
    user_sid = sa.Column(sa.String(length=255), nullable=True, index=True, unique=True)


class TwoFactorAuthModel(sa.Model):
    __tablename__ = 'system_twofactorauthentication'

    id = sa.Column(sa.Integer(), primary_key=True)
    otp_digits = sa.Column(sa.Integer(), default=6)
    window = sa.Column(sa.Integer(), default=0)
    interval = sa.Column(sa.Integer(), default=30)
    services = sa.Column(sa.JSON(), default={})
    enabled = sa.Column(sa.Boolean(), default=False)


class TwoFactorAuthService(ConfigService):

    class Config:
        datastore = 'system.twofactorauthentication'
        datastore_extend = 'auth.twofactor.two_factor_extend'
        namespace = 'auth.twofactor'
        cli_namespace = 'auth.two_factor'

    ENTRY = Dict(
        'auth_twofactor_entry',
        Bool('enabled', required=True),
        Int('otp_digits', validators=[Range(min=6, max=8)], required=True),
        Int('window', validators=[Range(min=0)], required=True),
        Int('interval', validators=[Range(min=5)], required=True),
        Dict(
            'services',
            Bool('ssh', default=False),
            required=True
        ),
        Int('id', required=True),
    )

    @private
    async def two_factor_extend(self, data):
        for srv in ['ssh']:
            data['services'].setdefault(srv, False)

        return data

    @accepts(
        Patch(
            'auth_twofactor_entry', 'auth_twofactor_update',
            ('rm', {'name': 'id'}),
            ('attr', {'update': True}),
        )
    )
    async def do_update(self, data):
        """
        `otp_digits` represents number of allowed digits in the OTP.

        `window` extends the validity to `window` many counter ticks before and after the current one.

        `interval` is time duration in seconds specifying OTP expiration time from it's creation time.
        """
        old_config = await self.config()
        config = old_config.copy()

        config.update(data)

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            config['id'],
            config
        )

        await self.middleware.call('service.reload', 'ssh')

        return await self.config()

    @private
    async def get_user_config(self, user_id, local_user):
        filters = [
            ['user', '=', user_id], ['user_sid', '=', None]
        ] if local_user else [['user_sid', '=', user_id], ['user', '=', None]]
        if config := await self.middleware.call('datastore.query', 'account.twofactor_user_auth', filters):
            return {
                **config[0],
                'exists': True,
            }
        else:
            return {
                'secret': None,
                filters[0][0]: user_id,
                'exists': False,
            }

    @private
    def generate_base32_secret(self):
        return pyotp.random_base32()

    @private
    def get_users_config(self):
        users = []
        mapping = {
            user['sid']: user for user in self.middleware.call_sync(
                'user.query', [['local', '=', False], ['sid', '!=', None]], {
                    'extra': {'additional_information': ['DS']},
                }
            )
        }
        for config in self.middleware.call_sync(
            'datastore.query', 'account.twofactor_user_auth', [['secret', '!=', None]]
        ):
            username = None
            if config['user']:
                username = config['user']['bsdusr_username']
            elif user := mapping.get(config['user_sid']):
                username = user['username']

            if username:
                users.append({
                    'username': username,
                    'secret_hex': base64.b16encode(base64.b32decode(config['secret'])).decode()
                })

        return users

    @private
    async def get_ad_users(self):
        return {
            entry['user_sid']: entry for entry in await self.middleware.call(
                'datastore.query', 'account.twofactor_user_auth', [['user_sid', '!=', None]]
            )
        }
