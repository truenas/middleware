import pyotp

import middlewared.sqlalchemy as sa

from middlewared.schema import accepts, Bool, Dict, Int, Patch, returns, Str
from middlewared.service import CallError, ConfigService, private
from middlewared.validators import Range


class TwoFactoryUserAuthModel(sa.Model):
    __tablename__ = 'account_twofactor_user_auth'

    id = sa.Column(sa.Integer(), primary_key=True)
    secret = sa.Column(sa.EncryptedText(), nullable=True, default=None)
    user_id = sa.Column(sa.ForeignKey('account_bsdusers.id', ondelete='CASCADE'), index=True, nullable=True)


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
        Str('secret', required=True, null=True),
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
            ('rm', {'name': 'secret'}),
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

        if config['enabled'] and not config['secret']:
            # Only generate a new secret on `enabled` when `secret` is not already set.
            # This will aid users not setting secret up again on their mobiles.
            config['secret'] = await self.middleware.run_in_thread(
                self.generate_base32_secret
            )

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            config['id'],
            config
        )

        await self.middleware.call('service.reload', 'ssh')

        return await self.config()

    @accepts(
        Str('token', null=True)
    )
    @returns(Bool('token_verified'))
    def verify(self, token):
        """
        Returns boolean true if provided `token` is successfully authenticated.
        """
        config = self.middleware.call_sync(f'{self._config.namespace}.config')
        if not config['enabled']:
            raise CallError('Please enable Two Factor Authentication first.')

        totp = pyotp.totp.TOTP(
            config['secret'], interval=config['interval'], digits=config['otp_digits']
        )
        return totp.verify(token, valid_window=config['window'])

    @accepts()
    @returns(Bool('successfully_renewed_secret'))
    def renew_secret(self):
        """
        Generates a new secret for Two Factor Authentication. Returns boolean true on success.
        """
        config = self.middleware.call_sync(f'{self._config.namespace}.config')
        if not config['enabled']:
            raise CallError('Please enable Two Factor Authentication first.')

        self.middleware.call_sync(
            'datastore.update',
            self._config.datastore,
            config['id'], {
                'secret': self.generate_base32_secret()
            }
        )

        if config['services']['ssh']:
            self.middleware.call_sync('service.reload', 'ssh')

        return True

    @accepts()
    @returns(Str(title='Provisioning URI'))
    async def provisioning_uri(self):
        """
        Returns the provisioning URI for the OTP. This can then be encoded in a QR Code and used to
        provision an OTP app like Google Authenticator.
        """
        config = await self.middleware.call(f'{self._config.namespace}.config')
        return pyotp.totp.TOTP(
            config['secret'], interval=config['interval'], digits=config['otp_digits']
        ).provisioning_uri(
            f'{await self.middleware.call("system.hostname")}@{await self.middleware.call("system.product_name")}',
            'iXsystems'
        )

    @private
    def generate_base32_secret(self):
        return pyotp.random_base32()
