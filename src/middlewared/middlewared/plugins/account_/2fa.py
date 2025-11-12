import errno

from pydantic import Secret
import pyotp

from middlewared.api import api_method
from middlewared.api.base import BaseModel, single_argument_result
from middlewared.api.current import (
    UserTwofactorConfigEntry, UserUnset2faSecretArgs, UserUnset2faSecretResult,
    UserRenew2faSecretArgs, UserRenew2faSecretResult
)
from middlewared.service import CallError, private, Service
from middlewared.utils import ProductName
from middlewared.utils.privilege import app_credential_full_admin_or_user


class UserProvisioningUriArgs(BaseModel):
    username: str


class UserProvisioningUriResult(BaseModel):
    result: str


class UserTwofactorConfigArgs(BaseModel):
    username: str


@single_argument_result
class UserTwofactorConfigResult(UserTwofactorConfigEntry):
    pass


class UserVerifyTwofactorTokenArgs(BaseModel):
    username: str
    token: Secret[str | None] = None


class UserVerifyTwofactorTokenResult(BaseModel):
    result: bool


class UserService(Service):

    @private
    async def provisioning_uri_internal(self, username, user_twofactor_config):
        return pyotp.totp.TOTP(
            user_twofactor_config['secret'], interval=user_twofactor_config['interval'],
            digits=user_twofactor_config['otp_digits'],
        ).provisioning_uri(
            f'{username}-{await self.middleware.call("system.hostname")}'
            f'@{ProductName.PRODUCT_NAME}',
            'iXsystems'
        )

    @api_method(UserProvisioningUriArgs, UserProvisioningUriResult, private=True)
    async def provisioning_uri(self, username):
        """
        Returns the provisioning URI for the OTP for `username`. This can then be encoded in a QR code and used
        to provision an OTP app like Google Authenticator.

        WARNING: response for this endpoint includes the 2FA secret for the user
        """
        user = await self.translate_username(username)
        user_twofactor_config = await self.middleware.call(
            'auth.twofactor.get_user_config', user['id' if user['local'] else 'sid'], user['local'],
        )
        if not user_twofactor_config['secret']:
            raise CallError(f'{user["username"]!r} user does not have two factor authentication configured')

        return await self.provisioning_uri_internal(username, user_twofactor_config)

    @api_method(UserTwofactorConfigArgs, UserTwofactorConfigResult, private=True)
    async def twofactor_config(self, username):
        """
        Returns two-factor authentication configuration settings for specified `username`.

        WARNING: response for this endpoint includes the 2FA secret for the user
        """
        user = await self.translate_username(username)
        user_twofactor_config = await self.middleware.call(
            'auth.twofactor.get_user_config', user['id' if user['local'] else 'sid'], user['local'],
        )
        if user_twofactor_config['secret']:
            provisioning_uri = await self.provisioning_uri_internal(username, user_twofactor_config)
        else:
            provisioning_uri = None

        return {
            'provisioning_uri': provisioning_uri,
            'secret_configured': bool(user_twofactor_config['secret']),
            'interval': user_twofactor_config['interval'],
            'otp_digits': user_twofactor_config['otp_digits'],
        }

    @api_method(UserVerifyTwofactorTokenArgs, UserVerifyTwofactorTokenResult, private=True)
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
            user_twofactor_config['secret'], interval=user_twofactor_config['interval'],
            digits=user_twofactor_config['otp_digits'],
        )
        return totp.verify(token or '', valid_window=twofactor_config['window'])

    @private
    async def translate_username(self, username):
        """
        Translates `username` to a user object.
        """
        try:
            user = await self.middleware.call('user.get_user_obj', {'username': username})
        except KeyError:
            raise CallError(f'User {username!r} does not exist', errno.ENOENT)

        return await self.middleware.call('user.query', [['username', '=', user['pw_name']]], {'get': True})

    @api_method(UserUnset2faSecretArgs, UserUnset2faSecretResult,
                audit='Unset two-factor authentication secret:',
                audit_extended=lambda username: username,
                roles=['ACCOUNT_WRITE'])
    async def unset_2fa_secret(self, username):
        """
        Unset two-factor authentication secret for `username`.
        """
        user = await self.translate_username(username)
        twofactor_auth = await self.middleware.call(
            'auth.twofactor.get_user_config', user['id' if user['local'] else 'sid'], user['local']
        )
        if not twofactor_auth['exists']:
            # This will only happen for AD users and we don't have a db record for them until they configure 2fa
            # in this case we don't do anything and the secret is already unset
            return

        await self.middleware.call(
            'datastore.update',
            'account.twofactor_user_auth',
            twofactor_auth['id'], {
                'secret': None,
            }
        )

        # We need to regenerate the users.oath file in order to remove
        # 2FA requirement for the user
        await self.middleware.call('etc.generate', 'user')

    @api_method(
        UserRenew2faSecretArgs,
        UserRenew2faSecretResult,
        audit='Renew two-factor authentication secret:',
        audit_extended=lambda username, options: username,
        authorization_required=False,
        pass_app=True,
    )
    async def renew_2fa_secret(self, app, username, twofactor_options):
        """
        Renew `username` user's two-factor authentication secret.

        NOTE: This username must match the authenticated username unless authenticated
        credentials have FULL_ADMIN role.
        """
        if not app_credential_full_admin_or_user(app, username):
            raise CallError(
                f'{username}: currently authenticated credential may not renew two-factor '
                'authentication for this user.',
                errno.EPERM
            )

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
                    **twofactor_options,
                }
            )
        else:
            await self.middleware.call(
                'datastore.insert', 'account.twofactor_user_auth', {
                    'secret': secret,
                    'user': None,
                    'user_sid': user['sid'],
                    **twofactor_options,
                }
            )

        if (await self.middleware.call('auth.twofactor.config'))['services']['ssh']:
            # This needs to be reloaded so that user's new secret can be reflected in sshd configuration
            await (await self.middleware.call('service.control', 'RELOAD', 'ssh')).wait(raise_error=True)

        user_entry = await self.translate_username(username)
        twofactor_config = await self.twofactor_config(username)
        await self.middleware.call('etc.generate', 'user')
        return user_entry | {'twofactor_config': twofactor_config}
