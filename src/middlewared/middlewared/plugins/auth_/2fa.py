import base64
import contextlib
import pyotp

import middlewared.sqlalchemy as sa

from middlewared.api import api_method
from middlewared.api.current import TwoFactorAuthEntry, TwoFactorAuthUpdateArgs, TwoFactorAuthUpdateResult
from middlewared.service import CallError, ConfigService, periodic, private
from middlewared.service_exception import ValidationErrors
from middlewared.utils.directoryservices.constants import DSStatus, DSType


class TwoFactoryUserAuthModel(sa.Model):
    __tablename__ = 'account_twofactor_user_auth'

    id = sa.Column(sa.Integer(), primary_key=True)
    secret = sa.Column(sa.EncryptedText(), nullable=True, default=None)
    user_id = sa.Column(sa.ForeignKey('account_bsdusers.id', ondelete='CASCADE'), index=True, nullable=True)
    user_sid = sa.Column(sa.String(length=255), nullable=True, index=True, unique=True)
    otp_digits = sa.Column(sa.Integer(), default=6)
    interval = sa.Column(sa.Integer(), default=30)


class TwoFactorAuthModel(sa.Model):
    __tablename__ = 'system_twofactorauthentication'

    id = sa.Column(sa.Integer(), primary_key=True)
    services = sa.Column(sa.JSON(), default={})
    enabled = sa.Column(sa.Boolean(), default=False)
    window = sa.Column(sa.Integer(), default=0)


class TwoFactorAuthService(ConfigService):

    class Config:
        datastore = 'system.twofactorauthentication'
        datastore_extend = 'auth.twofactor.two_factor_extend'
        namespace = 'auth.twofactor'
        cli_namespace = 'auth.two_factor'
        role_prefix = 'SYSTEM_SECURITY'
        entry = TwoFactorAuthEntry

    @private
    async def two_factor_extend(self, data):
        for srv in ['ssh']:
            data['services'].setdefault(srv, False)

        return data

    @api_method(
        TwoFactorAuthUpdateArgs,
        TwoFactorAuthUpdateResult,
        audit='Update two-factor authentication service configuration'
    )
    async def do_update(self, data):
        """
        `window` extends the validity to `window` many counter ticks before and after the current one.

        Update Two-Factor Authentication Service Configuration.
        """
        verrors = ValidationErrors()
        security = await self.middleware.call('system.security.config')

        old_config = await self.config()
        config = old_config.copy()

        config.update(data)

        if security['enable_gpos_stig']:
            if not config['enabled']:
                verrors.add(
                    'auth_twofactor_update.enable',
                    'Two factor authentication may not be disabled in General Purpose OS STIG mode.'
                )

            if not config['services']['ssh']:
                verrors.add(
                    'auth_twofactor_update.services.ssh',
                    'Two factor authentication for ssh service is required in General Purpose OS STIG mode.'
                )

        verrors.check()
        if config == old_config:
            return config

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            config['id'],
            config
        )

        # It's possible we have stale authenticator assurance level. An example is
        # we were standby controller and for some reason a reboot failed after disabling
        # STIG, then the admin chooses to fail over manually to server in unclean state
        # We know that AAL has to be level 1 when 2FA is disabled
        if not config['enabled']:
            await self.middleware.call('auth.set_authenticator_assurance_level', 'LEVEL_1')

        for svc in ('ssh', 'user'):
            # Going through service.control ensures HA is handled.
            await (await self.middleware.call('service.control', 'RELOAD', svc)).wait(raise_error=True)

        await self.middleware.call('etc.generate', 'pam_middleware')

        return await self.config()

    @private
    async def get_user_config(self, user_id, local_user):
        filters = [
            ['user_id', '=', user_id], ['user_sid', '=', None]
        ] if local_user else [['user_sid', '=', user_id], ['user_id', '=', None]]
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
                'interval': 30,
                'otp_digits': 6,
            }

    @private
    def generate_base32_secret(self):
        return pyotp.random_base32()

    @private
    def get_users_config(self):
        users = []
        mapping = {
            user['sid']: user for user in self.middleware.call_sync(
                'user.query', [['local', '=', False], ['sid', '!=', None]]
            )
        }
        for config in self.middleware.call_sync(
            'datastore.query', 'account.twofactor_user_auth', [['secret', '!=', None]]
        ):
            username = None
            ad_user = False
            if config['user']:
                username = config['user']['bsdusr_username']
            elif user := mapping.get(config['user_sid']):
                username = user['username']
                ad_user = True

            if username:
                users.append({
                    'username': username,
                    'secret_hex': base64.b16encode(base64.b32decode(config['secret'])).decode(),
                    'row_id': config['id'],
                    'ad_user': ad_user,
                    'otp_digits': config['otp_digits'],
                    'interval': config['interval']
                })

        return users

    @private
    async def get_ad_users(self):
        return {
            entry['user_sid']: entry for entry in await self.middleware.call(
                'datastore.query', 'account.twofactor_user_auth', [['user_sid', '!=', None]]
            )
        }

    @periodic(interval=86400, run_on_start=False)
    @private
    async def remove_expired_secrets(self):
        ds = await self.middleware.call('directoryservices.status')
        if ds['type'] != DSType.AD.value or ds['status'] != DSStatus.HEALTHY.name:
            return

        ad_users = await self.get_ad_users()
        ad_users_sid_mapping = {user['sid']: user for user in ad_users}

        with contextlib.suppress(CallError):
            for unmapped_user_sid in (await self.middleware.call('idmap.convert_sids', list(ad_users)))['unmapped']:
                await self.middleware.call(
                    'datastore.delete', 'account.twofactor_user_auth', ad_users_sid_mapping[unmapped_user_sid]['id']
                )
