import contextlib
import logging

from truenas_connect_utils.config import get_account_id_and_system_id
from truenas_connect_utils.status import Status
from truenas_connect_utils.urls import get_account_service_url

import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import (
    TNCEntry, TrueNASConnectUpdateArgs, TrueNASConnectUpdateResult,
    TrueNASConnectIpChoicesArgs, TrueNASConnectIpChoicesResult,
)
from middlewared.service import CallError, ConfigService, private, ValidationErrors

from .mixin import TNCAPIMixin
from .private_models import TrueNASConnectUpdateEnvironmentArgs, TrueNASConnectUpdateEnvironmentResult
from .utils import CLAIM_TOKEN_CACHE_KEY, get_unset_payload, TNC_IPS_CACHE_KEY


logger = logging.getLogger('truenas_connect')


class TrueNASConnectModel(sa.Model):
    __tablename__ = 'truenas_connect'

    id = sa.Column(sa.Integer(), primary_key=True)
    enabled = sa.Column(sa.Boolean(), default=False, nullable=False)
    jwt_token = sa.Column(sa.EncryptedText(), default=None, nullable=True)
    registration_details = sa.Column(sa.JSON(dict), nullable=False)
    ips = sa.Column(sa.JSON(list), nullable=False)
    interfaces = sa.Column(sa.JSON(list), nullable=False, default=list)
    interfaces_ips = sa.Column(sa.JSON(list), nullable=False, default=list)
    use_all_interfaces = sa.Column(sa.Boolean(), default=True, nullable=False)
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

        # Ensure at least one interface or at least one IP is provided (unless use_all_interfaces is True)
        if data['enabled'] and not data['ips'] and not data['interfaces'] and not data['use_all_interfaces']:
            verrors.add(
                'tn_connect_update',
                'At least one IP or interface must be provided when TrueNAS Connect is enabled '
                '(or use_all_interfaces must be set to true)'
            )

        data['ips'] = [str(ip) for ip in data['ips']]

        if data['interfaces']:
            all_interfaces = await self.middleware.call('interface.query', [], {'extra': {'retrieve_names_only': True}})
            interface_names = {iface['name'] for iface in all_interfaces}

            for interface in data['interfaces']:
                if interface not in interface_names:
                    verrors.add('tn_connect_update.interfaces', f'Interface "{interface}" does not exist')

            # If no direct IPs are provided, ensure selected interfaces have at least one IP
            if data['enabled'] and not data['ips'] and data['use_all_interfaces'] is False:
                interface_ips = await self.get_interface_ips(data['interfaces'])
                if not interface_ips:
                    verrors.add(
                        'tn_connect_update.interfaces',
                        'Selected interfaces must have at least one IP address configured'
                    )

        ips_changed = set(old_config['ips']) != set(data['ips'])
        interfaces_changed = set(old_config.get('interfaces', [])) != set(data.get('interfaces', []))
        interfaces_changed |= old_config['use_all_interfaces'] != data['use_all_interfaces']

        if (ips_changed or interfaces_changed) and (
            data['enabled'] is True and old_config['status'] not in (Status.DISABLED.name, Status.CONFIGURED.name)
        ):
            verrors.add(
                'tn_connect_update',
                'IPs and interfaces settings cannot be changed when TrueNAS Connect is in a state '
                'other than disabled or completely configured'
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
            'interfaces': data['interfaces'],
            'use_all_interfaces': data['use_all_interfaces'],
        }
        restart_ui = False

        # Extract IPs from interfaces using ip_in_use method
        # If use_all_interfaces is True, get IPs from all interfaces
        if db_payload['use_all_interfaces']:
            db_payload['interfaces_ips'] = await self.get_all_interface_ips()
        else:
            db_payload['interfaces_ips'] = await self.get_interface_ips(db_payload['interfaces'])
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
            restart_ui = True

        # Check if IPs or interfaces have changed
        combined_ips_old = config['ips'] + config.get('interfaces_ips', [])
        combined_ips_new = db_payload['ips'] + db_payload['interfaces_ips']

        if (
            config['status'] == Status.CONFIGURED.name and db_payload.get(
                'status', Status.CONFIGURED.name
            ) == Status.CONFIGURED.name
        ) and set(combined_ips_old) != set(combined_ips_new):
            # Make sure we remove TNC IPs cache if IPs have changed
            with contextlib.suppress(KeyError):
                await self.middleware.call('cache.pop', TNC_IPS_CACHE_KEY)

            # Send combined IPs to TNC service
            response = await self.middleware.call('tn_connect.hostname.register_update_ips', combined_ips_new)
            if response['error']:
                raise CallError(f'Failed to update IPs with TrueNAS Connect: {response["error"]}')

        await self.middleware.call('datastore.update', self._config.datastore, config['id'], db_payload)

        if restart_ui:
            logger.debug('Restarting nginx to not use TNC certificate anymore')
            await self.middleware.call('system.general.ui_restart', 4)

        new_config = await self.config()
        self.middleware.send_event('tn_connect.config', 'CHANGED', fields=new_config)

        return new_config

    @api_method(TrueNASConnectUpdateEnvironmentArgs, TrueNASConnectUpdateEnvironmentResult, private=True)
    async def update_environment(self, data):
        config = await self.middleware.call('tn_connect.config')
        verrors = ValidationErrors()
        if config['enabled']:
            for k in filter(
                lambda k: k in data,
                ('account_service_base_url', 'leca_service_base_url', 'tnc_base_url', 'heartbeat_url')
            ):
                if data[k] != config[k]:
                    verrors.add(
                        f'tn_connect_update_environment.{k}',
                        'This field cannot be changed when TrueNAS Connect is enabled'
                    )

        verrors.check()

        # Update the config with the new data
        await self.middleware.call('datastore.update', self._config.datastore, config['id'], data)

        return await self.middleware.call('tn_connect.config')

    @private
    async def get_interface_ips(self, interfaces):
        """
        Returns a list of IPs for the given interfaces.
        """
        if not interfaces:
            return []

        ip_data = await self.middleware.call('interface.ip_in_use', {
            'ipv4': True,
            'ipv6': True,
            'ipv6_link_local': False,
            'interfaces': interfaces,
            'static': False,
            'loopback': False,
            'any': False,
        })
        return [ip['address'] for ip in ip_data]

    @private
    async def get_all_interface_ips(self):
        """
        Returns a list of IPs from all interfaces.
        """
        # Get all interface names
        all_interfaces = await self.middleware.call('interface.query', [], {'extra': {'retrieve_names_only': True}})
        interface_names = [iface['name'] for iface in all_interfaces]

        # Get IPs from all interfaces
        return await self.get_interface_ips(interface_names)

    @private
    async def unset_registration_details(self, revoke_cert_and_account=True):
        logger.debug('Unsetting registration details')
        for k in (CLAIM_TOKEN_CACHE_KEY, TNC_IPS_CACHE_KEY):
            with contextlib.suppress(KeyError):
                await self.middleware.call('cache.pop', k)

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
            if revoke_cert_and_account:
                logger.debug('Revoking existing TNC cert')
                await self.middleware.call('tn_connect.acme.revoke_cert')

        if revoke_cert_and_account is False:
            # This happens when we get 401 from heartbeat as TNC will already have caatered to these cases
            logger.debug('Skipping revoking TNC user account')
            return

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
