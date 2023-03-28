import pyotp

from middlewared.schema import accepts, Bool, returns, Str
from middlewared.service import CallError, Service


class UserService(Service):

    @accepts(Str('username'))
    @returns(Str(title='Provisioning URI'))
    async def provisioning_uri(self, username):
        """
        Returns the provisioning URI for the OTP for `username`. This can then be encoded in a QR code and used
        to provision an OTP app like Google Authenticator.
        """
        user = await self.middleware.call('user.query', [['username', '=', username]], {'get': True})
        twofactor_config = await self.middleware.call('auth.twofactor.config')
        user_twofactor_config = await self.middleware.call('auth.twofactor.get_user_config', user['id'])
        if not user_twofactor_config['secret']:
            raise CallError(f'{user["username"]!r} user does not has two factor authentication configured')

        return pyotp.totp.TOTP(
            user_twofactor_config['secret'], interval=twofactor_config['interval'],
            digits=twofactor_config['otp_digits'],
        ).provisioning_uri(
            f'{await self.middleware.call("system.hostname")}@{await self.middleware.call("system.product_name")}',
            'iXsystems'
        )

    @accepts(Str('username'), Str('token', null=True))
    @returns(Bool('token_verified'))
    def verify_twofactor_token(self, username, token):
        """
        Returns boolean true if provided `token` is successfully authenticated for `username`.
        """
        twofactor_config = self.middleware.call_sync('auth.twofactor.config')
        if not twofactor_config['enabled']:
            raise CallError('Please enable Two Factor Authentication first')

        user = await self.middleware.call('user.query', [['id', '=', username]], {'get': True})
        user_twofactor_config = self.middleware.call_sync('auth.twofactor.get_user_config', user['id'])
        totp = pyotp.totp.TOTP(
            user_twofactor_config['secret'], interval=twofactor_config['interval'],
            digits=twofactor_config['otp_digits'],
        )
        return totp.verify(token or '', valid_window=twofactor_config['window'])
