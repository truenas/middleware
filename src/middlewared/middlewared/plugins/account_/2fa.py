import errno
import pyotp

from middlewared.schema import accepts, Bool, Ref, returns, Str
from middlewared.service import CallError, private, Service


class UserService(Service):

    @accepts(Str('username'))
    @returns(Str(title='Provisioning URI'))
    async def provisioning_uri(self, username):
        """
        Returns the provisioning URI for the OTP for `username`. This can then be encoded in a QR code and used
        to provision an OTP app like Google Authenticator.
        """
        user = await self.translate_username(username)
        twofactor_config = await self.middleware.call('auth.twofactor.config')
        user_twofactor_config = await self.middleware.call(
            'auth.twofactor.get_user_config', user['id' if user['local'] else 'sid'], user['local'],
        )
        if not user_twofactor_config['secret']:
            raise CallError(f'{user["username"]!r} user does not have two factor authentication configured')

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

        user = self.middleware.call_sync('user.translate_username', username)
        if not user['twofactor_auth_configured']:
            raise CallError('Two Factor Authentication is not configured for this user')

        user_twofactor_config = self.middleware.call_sync(
            'auth.twofactor.get_user_config', user['id' if user['local'] else 'sid'], user['local'],
        )
        totp = pyotp.totp.TOTP(
            user_twofactor_config['secret'], interval=twofactor_config['interval'],
            digits=twofactor_config['otp_digits'],
        )
        return totp.verify(token or '', valid_window=twofactor_config['window'])

    @private
    async def translate_username(self, username):
        """
        Translates `username` to a user object.
        """
        try:
            user = await self.middleware.call('user.get_user_obj', {'username': username, 'sid_info': True})
        except KeyError:
            raise CallError(f'User {username!r} does not exist', errno.ENOENT)

        return await self.middleware.call(
            'user.query', [['username', '=', user['pw_name']]], {
                'get': True,
                'extra': {'additional_information': ['DS', 'SMB']},
            }
        )

    @accepts(Str('username'))
    @returns()
    async def unset_2fa_secret(self, username):
        """
        Unset two-factor authentication secret for `username`.
        """
        user = await self.translate_username(username)
        twofactor_auth = await self.middleware.call(
            'auth.twofactor.get_user_config', user['id' if user['local'] else 'sid'], user['local']
        )
        if not twofactor_auth['exists']:
            raise CallError(f'Unable to locate two factor authentication configuration for {username!r} user')

        twofactor_config = self.middleware.call_sync('auth.twofactor.config')
        if twofactor_config['enabled']:
            raise CallError('Please disable Two Factor Authentication first')

        await self.middleware.call(
            'datastore.update',
            'account.twofactor_user_auth',
            twofactor_auth['id'], {
                'secret': None,
            }
        )

    @accepts(Str('username'))
    @returns(Ref('user_entry'))
    async def renew_2fa_secret(self, username):
        """
        Renew `username` user's two-factor authentication secret.
        """
        user = await self.translate_username(username)
        twofactor_auth = await self.middleware.call(
            'auth.twofactor.get_user_config', user['id' if user['local'] else 'sid'], user['local']
        )

        # Add some sanity checks here
        # The sanity check is only for local users because they should always have a db record in our 2fa
        # table. For AD users, we don't have a db record for them until they configure 2fa explicitly.
        if user['local'] and not twofactor_auth['exists']:
            raise CallError(f'Unable to locate two factor authentication configuration for {username!r} user')

        secret = await self.middleware.call('auth.twofactor.generate_base32_secret')
        if twofactor_auth['exists']:
            await self.middleware.call(
                'datastore.update',
                'account.twofactor_user_auth',
                twofactor_auth['id'], {
                    'secret': secret,
                }
            )
        else:
            await self.middleware.call(
                'datastore.insert', 'account.twofactor_user_auth', {
                    'secret': secret,
                    'user': None,
                    'user_sid': user['sid'],
                }
            )

        return await self.translate_username(username)
