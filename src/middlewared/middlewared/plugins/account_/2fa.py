import pyotp

from middlewared.schema import accepts, Bool, Int, returns, Str
from middlewared.service import CallError, Service


class UserService(Service):

    @accepts(Int('user_id'))
    @returns(Str(title='Provisioning URI'))
    async def provisioning_uri(self, user_id):
        """
        Returns the provisioning URI for the OTP for `user_id`. This can then be encoded in a QR code and used
        to provision an OTP app like Google Authenticator.
        """
        user = await self.middleware.call('user.get_instance', user_id)
        twofactor_config = await self.middleware.call('auth.twofactor.config')
        user_twofactor_config = await self.middleware.call('auth.twofactor.get_user_twofactor_config', user_id)
        if not user_twofactor_config['secret']:
            raise CallError(f'{user["username"]!r} user does not has two factor authentication configured')

        return pyotp.totp.TOTP(
            user_twofactor_config['secret'], interval=twofactor_config['interval'],
            digits=twofactor_config['otp_digits'],
        ).provisioning_uri(
            f'{await self.middleware.call("system.hostname")}@{await self.middleware.call("system.product_name")}',
            'iXsystems'
        )

    @accepts(Int('user_id'), Str('token'))
    @returns(Bool('token_verified'))
    def verify_twofactor_token(self, user_id, token):
        """
        Returns boolean true if provided `token` is successfully authenticated for `user_id`.
        """
        twofactor_config = await self.middleware.call('auth.twofactor.config')
        if not twofactor_config['enabled']:
            raise CallError('Please enable Two Factor Authentication first')

        user_twofactor_config = await self.middleware.call('auth.twofactor.get_user_twofactor_config', user_id)
        totp = pyotp.totp.TOTP(
            user_twofactor_config['secret'], interval=twofactor_config['interval'],
            digits=twofactor_config['otp_digits'],
        )
        return totp.verify(token, valid_window=twofactor_config['window'])
