import asyncio

import middlewared.sqlalchemy as sa

from middlewared.api import api_method
from middlewared.api.current import (
    SystemGeneralEntry, SystemGeneralUpdateArgs, SystemGeneralUpdateResult,
    SystemGeneralCheckinWaitingArgs, SystemGeneralCheckinWaitingResult,
    SystemGeneralCheckinArgs, SystemGeneralCheckinResult,
)
from middlewared.async_validators import validate_port
from middlewared.service import ConfigService, private
from middlewared.utils import run
from middlewared.utils.service.settings import SettingsHelper

settings = SettingsHelper()


class SystemGeneralModel(sa.Model):
    __tablename__ = 'system_settings'

    id = sa.Column(sa.Integer(), primary_key=True)
    stg_guiaddress = sa.Column(sa.JSON(list), default=['0.0.0.0'])
    stg_guiv6address = sa.Column(sa.JSON(list), default=['::'])
    stg_guiallowlist = sa.Column(sa.JSON(list), default=[])
    stg_guiport = sa.Column(sa.Integer(), default=80)
    stg_guihttpsport = sa.Column(sa.Integer(), default=443)
    stg_guihttpsredirect = sa.Column(sa.Boolean(), default=False)
    stg_guihttpsprotocols = sa.Column(sa.JSON(list), default=['TLSv1', 'TLSv1.1', 'TLSv1.2', 'TLSv1.3'])
    stg_guix_frame_options = sa.Column(sa.String(120), default='SAMEORIGIN')
    stg_guiconsolemsg = sa.Column(sa.Boolean(), default=True)
    stg_kbdmap = sa.Column(sa.String(120), default='us')
    stg_timezone = sa.Column(sa.String(120), default='America/Los_Angeles')
    stg_wizardshown = sa.Column(sa.Boolean(), default=False)
    stg_pwenc_check = sa.Column(sa.String(100))
    stg_guicertificate_id = sa.Column(sa.ForeignKey('system_certificate.id'), index=True, nullable=True)
    stg_usage_collection = sa.Column(sa.Boolean(), nullable=True)
    stg_ds_auth = sa.Column(sa.Boolean(), default=False)


class SystemGeneralService(ConfigService):

    class Config:
        namespace = 'system.general'
        datastore = 'system.settings'
        datastore_prefix = 'stg_'
        datastore_extend = 'system.general.general_system_extend'
        cli_namespace = 'system.general'
        role_prefix = 'SYSTEM_GENERAL'
        entry = SystemGeneralEntry

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_datastore = {}
        self._rollback_timer = None
        self._changed_https_port = False, -1

    @private
    async def general_system_extend(self, data):
        for key in list(data.keys()):
            if key.startswith('gui'):
                data['ui_' + key[3:]] = data.pop(key)

        if data['ui_certificate']:
            data['ui_certificate'] = await self.middleware.call(
                'certificate.get_instance', data['ui_certificate']['id']
            )

        data['usage_collection_is_set'] = data['usage_collection'] is not None
        if data['usage_collection'] is None:
            # Under no circumstances under GPOS STIG mode should usage_collection show enabled
            security_config = await self.middleware.call('system.security.config')
            data['usage_collection'] = not security_config['enable_gpos_stig']

        data.pop('pwenc_check')

        return data

    @settings.fields_validator('ui_port', 'ui_address')
    async def _validate_ui_port_address(self, verrors, ui_port, ui_address):
        for ui_address in ui_address:
            verrors.extend(await validate_port(self.middleware, 'ui_port', ui_port, 'system.general', ui_address))

    @settings.fields_validator('ui_httpsport', 'ui_address')
    async def _validate_ui_httpsport_address(self, verrors, ui_httpsport, ui_address):
        for ui_address in ui_address:
            verrors.extend(await validate_port(self.middleware, 'ui_httpsport', ui_httpsport, 'system.general',
                                               ui_address))

    @settings.fields_validator('ui_port', 'ui_httpsport')
    async def _validate_ui_ports(self, verrors, ui_port, ui_httpsport):
        if ui_port == ui_httpsport:
            verrors.add('ui_port', 'Must be different from "ui_httpsport"')

    @settings.fields_validator('ds_auth')
    async def _validate_ds_auth(self, verrors, ds_auth):
        if ds_auth and not await self.middleware.call('system.is_enterprise'):
            verrors.add(
                'ds_auth',
                'Directory services authentication for UI and API access requires an Enterprise license.'
            )

    @settings.fields_validator('kbdmap')
    async def _validate_kbdmap(self, verrors, kbdmap):
        if kbdmap not in await self.middleware.call('system.general.kbdmap_choices'):
            verrors.add(
                'kbdmap',
                'Please enter a valid keyboard layout'
            )

    @settings.fields_validator('timezone')
    async def _validate_timezone(self, verrors, timezone):
        timezones = await self.middleware.call('system.general.timezone_choices')
        if timezone not in timezones:
            verrors.add(
                'timezone',
                'Timezone not known. Please select a valid timezone.'
            )

    @settings.fields_validator('ui_address', 'ui_v6address')
    async def _validate_ui_address(self, verrors, ui_address, ui_v6address):
        ip4_addresses_list = await self.middleware.call('system.general.ui_address_choices')
        ip6_addresses_list = await self.middleware.call('system.general.ui_v6address_choices')

        for ip4_address in ui_address:
            if ip4_address not in ip4_addresses_list:
                verrors.add(
                    'ui_address',
                    f'{ip4_address} ipv4 address is not associated with this machine'
                )

        for ip6_address in ui_v6address:
            if ip6_address not in ip6_addresses_list:
                verrors.add(
                    'ui_v6address',
                    f'{ip6_address} ipv6 address is not associated with this machine'
                )

        for key, wildcard, ips in [('ui_address', '0.0.0.0', ui_address), ('ui_v6address', '::', ui_v6address)]:
            if wildcard in ips and len(ips) > 1:
                verrors.add(
                    key,
                    f'When "{wildcard}" has been selected, selection of other addresses is not allowed'
                )

    @settings.fields_validator('ui_certificate')
    async def _validate_ui_certificate(self, verrors, ui_certificate):
        cert = await self.middleware.call(
            'certificate.query',
            [["id", "=", ui_certificate]]
        )
        if not cert:
            verrors.add(
                'ui_certificate',
                'Please specify a valid certificate which exists in the system'
            )
        else:
            verrors.extend(
                await self.middleware.call(
                    'certificate.cert_services_validation', ui_certificate, 'ui_certificate', False
                )
            )

    @settings.fields_validator('usage_collection')
    async def _validate_usage_collection(self, verrors, usage_collection):
        """ Cannot enable usage_collection when STIG is enabled """
        security_config = await self.middleware.call('system.security.config')
        if usage_collection and security_config['enable_gpos_stig']:
            verrors.add(
                'usage_collection',
                'Usage collection is not allowed in GPOS STIG mode',
            )

    @api_method(SystemGeneralUpdateArgs, SystemGeneralUpdateResult, audit='System general update')
    async def do_update(self, data):
        """
        Update System General Service Configuration.

        UI configuration is not applied automatically. Call `system.general.ui_restart` to apply new UI settings (all
        HTTP connections will be aborted) or specify `ui_restart_delay` (in seconds) to automatically apply them after
        some small amount of time necessary you might need to receive the response for your settings update request.

        If incorrect UI configuration is applied, you might loss API connectivity and won't be able to fix the settings.
        To avoid that, specify `rollback_timeout` (in seconds). It will automatically roll back UI configuration to the
        previously working settings after `rollback_timeout` passes unless you call `system.general.checkin` in case
        the new settings were correct and no rollback is necessary.
        """
        rollback_timeout = data.pop('rollback_timeout', None)
        ui_restart_delay = data.pop('ui_restart_delay', None)

        original_datastore = await self.middleware.call('datastore.config', self._config.datastore)
        original_datastore['stg_guicertificate'] = (
            original_datastore['stg_guicertificate']['id']
            if original_datastore['stg_guicertificate']
            else None
        )

        config = await self.config()
        config['ui_certificate'] = config['ui_certificate']['id'] if config['ui_certificate'] else None
        if not config.pop('usage_collection_is_set'):
            config['usage_collection'] = None
        new_config = config.copy()
        new_config.update(data)

        await settings.validate(self, 'general_settings', config, new_config)

        db_config = new_config.copy()
        for key in list(new_config.keys()):
            if key.startswith('ui_'):
                db_config['gui' + key[3:]] = db_config.pop(key)

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            config['id'],
            db_config,
            {'prefix': 'stg_'}
        )

        if config['kbdmap'] != new_config['kbdmap']:
            await self.set_kbdlayout()

        if config['timezone'] != new_config['timezone']:
            await self.middleware.call('zettarepl.update_config', {'timezone': new_config['timezone']})
            await (await self.middleware.call('service.control', 'RELOAD', 'timeservices')).wait(raise_error=True)
            await (await self.middleware.call('service.control', 'RESTART', 'cron')).wait(raise_error=True)

        if config['ds_auth'] != new_config['ds_auth']:
            await self.middleware.call('etc.generate', 'pam_middleware')

        self._changed_https_port = config['ui_httpsport'] != new_config['ui_httpsport'], new_config['ui_httpsport']

        await (await self.middleware.call('service.control', 'START', 'ssl')).wait(raise_error=True)

        if rollback_timeout is not None:
            self._original_datastore = original_datastore
            self._rollback_timer = asyncio.get_event_loop().call_later(
                rollback_timeout,
                lambda: self.middleware.create_task(self.rollback()),
            )

        if ui_restart_delay is not None:
            await self.middleware.call('system.general.ui_restart', ui_restart_delay)

        for key in ('ui_port', 'ui_httpsport', 'ui_httpsredirect', 'ui_address', 'ui_v6address'):
            if config[key] != new_config[key]:
                await self.middleware.call('system.reload_cli')
                break

        return await self.config()

    @private
    async def set_kbdlayout(self):
        await self.middleware.call('etc.generate', 'keyboard')
        await run(['setupcon'], check=False)
        await self.middleware.call('boot.update_initramfs', {'force': True})

    @api_method(SystemGeneralCheckinWaitingArgs, SystemGeneralCheckinWaitingResult, roles=['SYSTEM_GENERAL_WRITE'])
    async def checkin_waiting(self):
        """
        Determines whether we are waiting user to check in the applied UI settings changes before they are rolled
        back. Returns a number of seconds before the automatic rollback or null if there are no changes pending.
        """
        if self._rollback_timer:
            remaining = self._rollback_timer.when() - asyncio.get_event_loop().time()
            if remaining > 0:
                return int(remaining)

    @api_method(SystemGeneralCheckinArgs, SystemGeneralCheckinResult, roles=['SYSTEM_GENERAL_WRITE'])
    async def checkin(self):
        """
        After UI settings are saved with `rollback_timeout` this method needs to be called within that timeout limit
        to prevent reverting the changes.

        This is to ensure user verifies the changes went as planned and its working.
        """
        if self._rollback_timer:
            self._rollback_timer.cancel()

        self._rollback_timer = None
        self._original_datastore = {}

    @private
    async def rollback(self):
        if self._original_datastore:
            await self.middleware.call(
                'datastore.update',
                self._config.datastore,
                self._original_datastore['id'],
                {k: v for k, v in self._original_datastore.items() if k.startswith('stg_gui')},
            )
            await self.middleware.call('system.general.ui_restart', 0)

            self._rollback_timer = None
            self._original_datastore = {}

    @private
    async def https_port_changed(self) -> tuple[bool, int]:
        return self._changed_https_port
