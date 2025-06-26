import contextlib
import logging

from truenas_connect_utils.config import get_account_id_and_system_id
from truenas_connect_utils.status import Status
from truenas_connect_utils.urls import get_account_service_url

import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import TNCEntry, TrueNASConnectUpdateArgs, TrueNASConnectUpdateResult, TrueNASConnectIpChoicesArgs, TrueNASConnectIpChoicesResult
from middlewared.service import CallError, ConfigService, private, ValidationErrors

from .mixin import TNCAPIMixin
from .utils import CLAIM_TOKEN_CACHE_KEY, get_unset_payload


logger = logging.getLogger('truenas_connect')


class TrueNASConnectModel(sa.Model):
    __tablename__ = 'truenas_connect'

    id = sa.Column(sa.Integer(), primary_key=True)
    enabled = sa.Column(sa.Boolean(), default=False, nullable=False)
    jwt_token = sa.Column(sa.EncryptedText(), default=None, nullable=True)
    registration_details = sa.Column(sa.JSON(dict), nullable=False)
    ips = sa.Column(sa.JSON(list), nullable=False)
    status = sa.Column(sa.String(255), default=Status.DISABLED.name, nullable=False)
    certificate_id = sa.Column(sa.ForeignKey('system_certificate.id'), index=True, nullable=True)
    account_service_base_url = sa.Column(
        sa.String(255), nullable=False, default='https://account-service.staging.truenasconnect.net/'
    )
    leca_service_base_url = sa.Column(
        sa.String(255), nullable=False, default='https://dns-service.staging.truenasconnect.net/'
    )
    tnc_base_url = sa.Column(
        sa.String(255), nullable=False, default='https://web.staging.truenasconnect.net/'
    )
    heartbeat_url = sa.Column(
        sa.String(255), nullable=False, default='https://heartbeat-service.staging.truenasconnect.net/'
    )
    last_heartbeat_failure_datetime = sa.Column(sa.String(255), nullable=True, default=None)


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
        config.pop('last_heartbeat_failure_datetime', None)
        if config['certificate']:
            config['certificate'] = config['certificate']['id']
        return config

    @private
    async def validate_data(self, old_config, data):
        verrors = ValidationErrors()
        if data['enabled'] and not data['ips']:
            verrors.add('tn_connect_update.ips', 'This field is required when TrueNAS Connect is enabled')

        data['ips'] = [str(ip) for ip in data['ips']]

        ips_changed = set(old_config['ips']) != set(data['ips'])
        if ips_changed and (
            data['enabled'] is True and old_config['status'] not in (Status.DISABLED.name, Status.CONFIGURED.name)
        ):
            verrors.add(
                'tn_connect_update.ips',
                'IPs cannot be changed when TrueNAS Connect is in a state other than disabled or completely configured'
            )

        if data['enabled'] and old_config['enabled']:
            for k in ('account_service_base_url', 'leca_service_base_url', 'tnc_base_url', 'heartbeat_url'):
                if data[k] != old_config[k]:
                    verrors.add(
                        f'tn_connect_update.{k}', 'This field cannot be changed when TrueNAS Connect is enabled'
                    )

        verrors.check()

    @api_method(TrueNASConnectUpdateArgs, TrueNASConnectUpdateResult)
    async def do_update(self, data):
        """
        Update TrueNAS Connect configuration.
        """
        config = await self.config()
        data = config | data

        await self.validate_data(config, data)

        db_payload = {
            'enabled': data['enabled'],
            'ips': data['ips'],
        } | {k: data[k] for k in ('account_service_base_url', 'leca_service_base_url', 'tnc_base_url', 'heartbeat_url')}
        if config['enabled'] is False and data['enabled'] is True:
            # Finalization registration is triggered when claim token is generated
            # We make sure there is no pending claim token
            with contextlib.suppress(KeyError):
                await self.middleware.call('cache.pop', CLAIM_TOKEN_CACHE_KEY)
            db_payload['status'] = Status.CLAIM_TOKEN_MISSING.name
            logger.debug('Removing any stale TNC unconfigured alert or heartbeat alert')
            await self.middleware.call('alert.oneshot_delete', 'TNCDisabledAutoUnconfigured')
            await self.middleware.call('alert.oneshot_delete', 'TNCHeartbeatConnectionFailure')
        elif config['enabled'] is True and data['enabled'] is False:
            await self.unset_registration_details()
            db_payload.update(get_unset_payload())

        if (
            config['status'] == Status.CONFIGURED.name and db_payload.get(
                'status', Status.CONFIGURED.name
            ) == Status.CONFIGURED.name
        ) and config['ips'] != db_payload['ips']:
            response = await self.middleware.call('tn_connect.hostname.register_update_ips', db_payload['ips'])
            if response['error']:
                raise CallError(f'Failed to update IPs with TrueNAS Connect: {response["error"]}')

        await self.middleware.call('datastore.update', self._config.datastore, config['id'], db_payload)

        new_config = await self.config()
        self.middleware.send_event('tn_connect.config', 'CHANGED', fields=new_config)

        return new_config

    @private
    async def unset_registration_details(self):
        logger.debug('Unsetting registration details')
        with contextlib.suppress(KeyError):
            await self.middleware.call('cache.pop', CLAIM_TOKEN_CACHE_KEY)

        logger.debug('TNC is being disabled, removing any stale TNC heartbeat failure alert')
        await self.middleware.call('alert.oneshot_delete', 'TNCHeartbeatConnectionFailure')

        config = await self.config_internal()
        creds = get_account_id_and_system_id(config)
        if creds is None:
            return

        # If we have a cert set, we will try to revoke it and also update system to use system cert
        if config['certificate']:
            logger.debug('Setting up self generated cert for UI')
            await self.middleware.call('certificate.setup_self_signed_cert_for_ui')
            logger.debug('Restarting nginx to consume self generated cert')
            await self.middleware.call('system.general.ui_restart', 2)
            logger.debug('Revoking existing TNC cert')
            await self.middleware.call('tn_connect.acme.revoke_cert')

        logger.debug('Revoking TNC user account')
        # We need to revoke the user account now
        response = await self._call(
            get_account_service_url(config).format(**creds), 'delete', headers=await self.auth_headers(config),
        )
        if response['error']:
            if response['status_code'] == 401:
                # This can happen when user removed NAS from TNC UI, so we still want unset to proceed
                logger.error('Failed to revoke account with 401 status code: %s', response['error'])
            else:
                raise CallError(f'Failed to revoke account: {response["error"]}')

    @api_method(TrueNASConnectIpChoicesArgs, TrueNASConnectIpChoicesResult, roles=['TRUENAS_CONNECT_READ'])
    async def ip_choices(self):
        """
        Returns IP choices which can be used with TrueNAS Connect.
        """
        # This is used by UI to present some options to the user but user can choose any other
        # IP as well of course
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
    middleware.event_register(
        'tn_connect.config', 'Sent on TrueNAS Connect configuration changes', roles=['TRUENAS_CONNECT_READ']
    )
