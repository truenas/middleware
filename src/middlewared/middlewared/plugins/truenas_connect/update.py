import contextlib
import enum
import logging

from truenas_connect_utils.config import get_account_id_and_system_id
from truenas_connect_utils.status import Status
from truenas_connect_utils.urls import get_account_service_url

import middlewared.sqlalchemy as sa
from middlewared.api import api_method, Event
from middlewared.api.current import (
    TrueNASConnectEntry, TrueNASConnectUpdateArgs, TrueNASConnectUpdateResult,
    TrueNASConnectIpChoicesArgs, TrueNASConnectIpChoicesResult,
    TrueNASConnectConfigChangedEvent,
    TrueNASConnectIpsWithHostnamesArgs, TrueNASConnectIpsWithHostnamesResult,
)
from middlewared.service import CallError, ConfigService, private, ValidationErrors

from .mixin import TNCAPIMixin
from .private_models import TrueNASConnectUpdateEnvironmentArgs, TrueNASConnectUpdateEnvironmentResult
from .utils import CLAIM_TOKEN_CACHE_KEY, get_unset_payload, TNC_IPS_CACHE_KEY

logger = logging.getLogger('truenas_connect')


class TrueNASConnectTier(enum.IntEnum):
    FOUNDATION = 1
    PLUS = 2
    BUSINESS = 3


class TrueNASConnectModel(sa.Model):
    __tablename__ = 'truenas_connect'

    id = sa.Column(sa.Integer(), primary_key=True)
    enabled = sa.Column(sa.Boolean(), default=False, nullable=False)
    jwt_token = sa.Column(sa.EncryptedText(), default=None, nullable=True)
    registration_details = sa.Column(sa.JSON(dict), nullable=False)
    status = sa.Column(sa.String(255), default=Status.DISABLED.name, nullable=False)
    certificate_id = sa.Column(sa.ForeignKey('system_certificate.id'), index=True, nullable=True)
    account_service_base_url = sa.Column(
        sa.String(255), nullable=False, default='https://account-service.tys1.truenasconnect.net/'
    )
    leca_service_base_url = sa.Column(
        sa.String(255), nullable=False, default='https://dns-service.tys1.truenasconnect.net/'
    )
    tnc_base_url = sa.Column(
        sa.String(255), nullable=False, default='https://web.truenasconnect.net/'
    )
    heartbeat_url = sa.Column(
        sa.String(255), nullable=False, default='https://heartbeat-service.tys1.truenasconnect.net/'
    )
    last_heartbeat_failure_datetime = sa.Column(sa.String(255), nullable=True, default=None)


class TrueNASConnectService(ConfigService, TNCAPIMixin):

    class Config:
        datastore = 'truenas_connect'
        datastore_extend = 'tn_connect.config_extend'
        cli_private = True
        namespace = 'tn_connect'
        entry = TrueNASConnectEntry
        role_prefix = 'TRUENAS_CONNECT'
        events = [
            Event(
                name='tn_connect.config',
                description='Sent on TrueNAS Connect configuration changes',
                roles=['TRUENAS_CONNECT_READ'],
                models={
                    'CHANGED': TrueNASConnectConfigChangedEvent,
                },
            )
        ]

    @private
    async def config_extend(self, config):
        config['status_reason'] = Status[config['status']].value
        config.pop('jwt_token', None)
        if config['certificate']:
            config['certificate'] = config['certificate']['id']

        try:
            config['tier'] = TrueNASConnectTier(config['registration_details']['tier']).name
        except (KeyError, ValueError):
            config['tier'] = None

        return config

    @private
    async def ha_vips(self):
        vips = []
        for interface in await self.middleware.call('interface.query'):
            for vip_entry in interface.get('failover_virtual_aliases', []):
                vips.append(vip_entry['address'])
        return vips

    @private
    async def validate_data(self, data):
        verrors = ValidationErrors()
        if data['enabled']:
            if await self.middleware.call('system.is_ha_capable'):
                if not await self.ha_vips():
                    verrors.add(
                        'tn_connect_update.enabled',
                        'HA systems must be in a healthy state to enable TNC ensuring we have VIP available'
                    )
            else:
                effective_ips = await self.get_effective_ips()
                if not effective_ips:
                    verrors.add(
                        'tn_connect_update.enabled',
                        'System must have at least one IP address configured in System > General settings '
                        'to enable TrueNAS Connect'
                    )

        verrors.check()

    @api_method(TrueNASConnectUpdateArgs, TrueNASConnectUpdateResult, audit='TrueNAS Connect: Updating configuration')
    async def do_update(self, data):
        """
        Update TrueNAS Connect configuration.
        """
        config = await self.config()
        data = config | data

        await self.validate_data(data)

        db_payload = {
            'enabled': data['enabled'],
        }
        tnc_disabled = False

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
            tnc_disabled = True

        await self.middleware.call('datastore.update', self._config.datastore, config['id'], db_payload)

        if tnc_disabled:
            # If TNC is disabled and was enabled earlier, we will like to restart UI and delete TNC cert
            logger.debug('Restarting nginx to not use TNC certificate anymore')
            await self.middleware.call('system.general.ui_restart', 4)

            if config['certificate']:
                await self.delete_cert(config['certificate'])

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
    async def get_effective_ips(self):
        """
        Derive the IPs TNC should advertise from system.general UI binding config.

        - If ui_address contains '0.0.0.0' (wildcard), resolve to all IPv4 addresses on the system.
        - If ui_v6address contains '::' (wildcard), resolve to all non-link-local IPv6 addresses.
        - Otherwise, use the specific addresses configured in system.general directly.
        """
        config = await self.middleware.call('system.general.config')
        ips = []

        if '0.0.0.0' in config['ui_address']:
            ips.extend(
                ip['address'] for ip in await self.middleware.call('interface.ip_in_use', {
                    'ipv4': True, 'ipv6': False, 'ipv6_link_local': False,
                    'static': False, 'loopback': False, 'any': False,
                })
            )
        else:
            ips.extend(config['ui_address'])

        if '::' in config['ui_v6address']:
            ips.extend(
                ip['address'] for ip in await self.middleware.call('interface.ip_in_use', {
                    'ipv4': False, 'ipv6': True, 'ipv6_link_local': False,
                    'static': False, 'loopback': False, 'any': False,
                })
            )
        else:
            ips.extend(config['ui_v6address'])

        return ips

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

        if revoke_cert_and_account is False:
            # This happens when we get 401 from heartbeat as TNC will already have caatered to these cases
            logger.debug('Skipping revoking TNC user account')
            return

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

    @private
    async def delete_cert(self, cert_id):
        # We will like to remove the TNC cert now when TNC is disabled
        # We will not make this fatal in case user had it configured with some other plugin
        # before we had added validation to prevent users from doing that
        logger.debug('Deleting TNC certificate with id %d', cert_id)
        delete_job = await self.middleware.call('certificate.delete', cert_id, True)
        await delete_job.wait()
        if delete_job.error:
            logger.error('Failed to delete TNC certificate: %s', delete_job.error)

    @api_method(
        TrueNASConnectIpChoicesArgs, TrueNASConnectIpChoicesResult, roles=['TRUENAS_CONNECT_READ'], removed_in='v26',
    )
    async def ip_choices(self):
        """
        Returns IP choices which can be used with TrueNAS Connect.

        .. deprecated::
            TrueNAS Connect now derives IPs from System > General settings.
        """
        return {
            ip['address']: ip['address']
            for ip in await self.middleware.call('interface.ip_in_use', {'static': True, 'any': False})
        }

    @api_method(
        TrueNASConnectIpsWithHostnamesArgs, TrueNASConnectIpsWithHostnamesResult, roles=['TRUENAS_CONNECT_READ']
    )
    async def ips_with_hostnames(self):
        """
        Returns current mapping of ips configured with truenas connect against their hostnames.
        """
        hostname_config = await self.middleware.call('tn_connect.hostname.config')
        return {
            v: k for k, v in hostname_config['hostname_details'].items()
        } if hostname_config['error'] is None and hostname_config['hostname_configured'] else {}

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
