import contextlib

import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import TNCEntry, TNCUpdateArgs, TNCUpdateResult, TNCIPChoicesArgs, TNCIPChoicesResult
from middlewared.service import CallError, ConfigService, private, ValidationErrors

from .mixin import TNCAPIMixin
from .status_utils import Status
from .urls import ACCOUNT_SERVICE_URL
from .utils import CLAIM_TOKEN_CACHE_KEY, get_account_id_and_system_id


class TrueNASConnectModel(sa.Model):
    __tablename__ = 'truenas_connect'

    id = sa.Column(sa.Integer(), primary_key=True)
    enabled = sa.Column(sa.Boolean(), default=False, nullable=False)
    jwt_token = sa.Column(sa.EncryptedText(), default=None, nullable=True)
    registration_details = sa.Column(sa.JSON(dict), nullable=False)
    ips = sa.Column(sa.JSON(list), nullable=False)
    status = sa.Column(sa.String(255), default=Status.DISABLED.name, nullable=False)
    certificate_id = sa.Column(sa.ForeignKey('system_certificate.id'), index=True, nullable=True)


class TrueNASConnectService(ConfigService, TNCAPIMixin):

    class Config:
        datastore = 'truenas_connect'
        datastore_extend = 'tn_connect.config_extend'
        cli_private = True
        namespace = 'tn_connect'
        entry = TNCEntry
        role_prefix = 'TRUENAS_CONNECT'

    @private
    async def config_extend(self, config):
        config['status_reason'] = Status[config['status']].value
        config.pop('jwt_token', None)
        if config['certificate']:
            config['certificate'] = config['certificate']['id']
        return config

    @private
    async def validate_data(self, old_config, data):
        verrors = ValidationErrors()
        if data['enabled'] and not data['ips']:
            verrors.add('tn_connect_update.ips', 'This field is required when TrueNAS Connect is enabled')

        ip_choices = await self.ip_choices()
        for index, ip in enumerate(data['ips']):
            if ip not in ip_choices:
                verrors.add(f'tn_connect_update.ips.{index}', 'Provided IP is not valid')

        ips_changed = set(old_config['ips']) != set(data['ips'])
        if ips_changed and (
            data['enabled'] is True and old_config['status'] not in (Status.DISABLED.name, Status.CONFIGURED.name)
        ):
            verrors.add(
                'tn_connect_update.ips',
                'IPs cannot be changed when TrueNAS Connect is in a state other than disabled or completely configured'
            )

        verrors.check()

    @api_method(TNCUpdateArgs, TNCUpdateResult)
    async def do_update(self, data):
        """
        Update TrueNAS Connect configuration.
        """
        config = await self.config()
        data = config | data
        await self.validate_data(config, data)

        db_payload = {'enabled': data['enabled'], 'ips': data['ips']}
        if config['enabled'] is False and data['enabled'] is True:
            # Finalization registration is triggered when claim token is generated
            # We make sure there is no pending claim token
            with contextlib.suppress(KeyError):
                await self.middleware.call('cache.pop', CLAIM_TOKEN_CACHE_KEY)
            db_payload['status'] = Status.CLAIM_TOKEN_MISSING.name
        elif config['enabled'] is True and data['enabled'] is False:
            await self.unset_registration_details()
            db_payload.update({
                'registration_details': {},
                'jwt_token': None,
                'status': Status.DISABLED.name,
                'certificate': None,
            })

        await self.middleware.call('datastore.update', self._config.datastore, config['id'], db_payload)

        new_config = await self.config()
        self.middleware.send_event('tn_connect.config', 'CHANGED', fields=new_config)

        if new_config['status'] is Status.CONFIGURED.name and config['ips'] != new_config['ips']:
            # TODO: Please discuss what should be done if this errors out and how an automatic retrial
            #  should be set in place
            response = await self.middleware.call('tn_connect.hostname.register_update_ips')
            if response['error']:
                raise CallError(f'Failed to update IPs with TrueNAS Connect: {response["error"]}')

        # TODO: Handle the case where user imports same db in a different system

        return new_config

    @private
    async def unset_registration_details(self):
        with contextlib.suppress(KeyError):
            await self.middleware.call('cache.pop', CLAIM_TOKEN_CACHE_KEY)

        config = await self.config_internal()
        creds = get_account_id_and_system_id(config)
        if creds is None:
            return

        # If we have a cert set, we will try to revoke it
        if config['certificate']:
            await self.middleware.call('tn_connect.acme.revoke_cert')

        # We need to revoke the user account now
        response = await self._call(
            ACCOUNT_SERVICE_URL.format(**creds), 'delete', headers=await self.auth_headers(config),
        )
        if response['error']:
            raise CallError(f'Failed to revoke account: {response["error"]}')

    @api_method(TNCIPChoicesArgs, TNCIPChoicesResult, roles=['TRUENAS_CONNECT_READ'])
    async def ip_choices(self):
        """
        Returns IP choices which can be used with TrueNAS Connect.
        """
        return {
            ip['address']: ip['address']
            for ip in await self.middleware.call('interface.ip_in_use', {'static': True, 'any': False})
        }

    @private
    async def set_status(self, new_status, db_payload=None):
        assert new_status in Status.__members__
        config = await self.config()
        await self.middleware.call(
            'datastore.update', self._config.datastore, config['id'], {'status': new_status} | (db_payload or {})
        )
        self.middleware.send_event('tn_connect.config', 'CHANGED', fields=(await self.config()))

    @private
    async def config_internal(self):
        config = await self.config()
        return (await self.middleware.call('datastore.config', self._config.datastore)) | config


async def setup(middleware):
    middleware.event_register('tn_connect.config', 'Sent on TrueNAS Connect configuration changes')
