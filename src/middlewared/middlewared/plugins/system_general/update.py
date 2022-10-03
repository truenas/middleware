import asyncio
import syslog

import middlewared.sqlalchemy as sa

from middlewared.async_validators import validate_port
from middlewared.logger import CrashReporting
from middlewared.schema import accepts, Bool, Datetime, Dict, Int, IPAddr, List, Patch, returns, Str
from middlewared.service import ConfigService, private, ValidationErrors
from middlewared.utils import run
from middlewared.validators import Range

from .utils import HTTPS_PROTOCOLS


class SystemGeneralModel(sa.Model):
    __tablename__ = 'system_settings'

    id = sa.Column(sa.Integer(), primary_key=True)
    stg_guiaddress = sa.Column(sa.JSON(type=list), default=['0.0.0.0'])
    stg_guiv6address = sa.Column(sa.JSON(type=list), default=['::'])
    stg_guiallowlist = sa.Column(sa.JSON(type=list), default=[])
    stg_guiport = sa.Column(sa.Integer(), default=80)
    stg_guihttpsport = sa.Column(sa.Integer(), default=443)
    stg_guihttpsredirect = sa.Column(sa.Boolean(), default=False)
    stg_guihttpsprotocols = sa.Column(sa.JSON(type=list), default=['TLSv1', 'TLSv1.1', 'TLSv1.2', 'TLSv1.3'])
    stg_guix_frame_options = sa.Column(sa.String(120), default='SAMEORIGIN')
    stg_guiconsolemsg = sa.Column(sa.Boolean(), default=True)
    stg_language = sa.Column(sa.String(120), default='en')
    stg_kbdmap = sa.Column(sa.String(120), default='us')
    stg_birthday = sa.Column(sa.DateTime(), nullable=True)
    stg_timezone = sa.Column(sa.String(120), default='America/Los_Angeles')
    stg_wizardshown = sa.Column(sa.Boolean(), default=False)
    stg_pwenc_check = sa.Column(sa.String(100))
    stg_guicertificate_id = sa.Column(sa.ForeignKey('system_certificate.id'), index=True, nullable=True)
    stg_crash_reporting = sa.Column(sa.Boolean(), nullable=True)
    stg_usage_collection = sa.Column(sa.Boolean(), nullable=True)
    stg_ds_auth = sa.Column(sa.Boolean(), default=False)


class SystemGeneralService(ConfigService):

    class Config:
        namespace = 'system.general'
        datastore = 'system.settings'
        datastore_prefix = 'stg_'
        datastore_extend = 'system.general.general_system_extend'
        cli_namespace = 'system.general'

    ENTRY = Dict(
        'system_general_entry',
        Patch(
            'certificate_entry', 'ui_certificate',
            ('attr', {'null': True, 'required': True}),
        ),
        Int('ui_httpsport', validators=[Range(min=1, max=65535)], required=True),
        Bool('ui_httpsredirect', required=True),
        List(
            'ui_httpsprotocols', items=[Str('protocol', enum=HTTPS_PROTOCOLS)],
            empty=False, unique=True, required=True
        ),
        Int('ui_port', validators=[Range(min=1, max=65535)], required=True),
        List('ui_address', items=[IPAddr('addr')], empty=False, required=True),
        List('ui_v6address', items=[IPAddr('addr')], empty=False, required=True),
        List('ui_allowlist', items=[IPAddr('addr', network=True, network_strict=True)], required=True),
        Bool('ui_consolemsg', required=True),
        Str('ui_x_frame_options', enum=['SAMEORIGIN', 'DENY', 'ALLOW_ALL'], required=True),
        Str('kbdmap', required=True),
        Str('language', empty=False, required=True),
        Str('timezone', empty=False, required=True),
        Bool('crash_reporting', null=True, required=True),
        Bool('usage_collection', null=True, required=True),
        Datetime('birthday', required=True),
        Bool('wizardshown', required=True),
        Bool('crash_reporting_is_set', required=True),
        Bool('usage_collection_is_set', required=True),
        Bool('ds_auth', required=True),
        Int('id', required=True),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_datastore = {}
        self._rollback_timer = None

    @private
    async def general_system_extend(self, data):
        for key in list(data.keys()):
            if key.startswith('gui'):
                data['ui_' + key[3:]] = data.pop(key)

        if data['ui_certificate']:
            data['ui_certificate'] = await self.middleware.call(
                'certificate.get_instance', data['ui_certificate']['id']
            )

        data['crash_reporting_is_set'] = data['crash_reporting'] is not None
        if data['crash_reporting'] is None:
            data['crash_reporting'] = True

        data['usage_collection_is_set'] = data['usage_collection'] is not None
        if data['usage_collection'] is None:
            data['usage_collection'] = True

        data.pop('pwenc_check')

        return data

    @private
    async def validate_general_settings(self, data, schema):
        verrors = ValidationErrors()

        for k in ('ui_port', 'ui_httpsport'):
            verrors.extend(await validate_port(self.middleware, f'{schema}.{k}', data[k], 'system.general'))

        language = data.get('language')
        system_languages = await self.middleware.call('system.general.language_choices')
        if language not in system_languages.keys():
            verrors.add(
                f'{schema}.language',
                f'Specified "{language}" language unknown. Please select a valid language.'
            )

        if data['kbdmap'] not in await self.middleware.call('system.general.kbdmap_choices'):
            verrors.add(
                f'{schema}.kbdmap',
                'Please enter a valid keyboard layout'
            )

        timezone = data.get('timezone')
        timezones = await self.middleware.call('system.general.timezone_choices')
        if timezone not in timezones:
            verrors.add(
                f'{schema}.timezone',
                'Timezone not known. Please select a valid timezone.'
            )

        ip4_addresses_list = await self.middleware.call('system.general.ui_address_choices')
        ip6_addresses_list = await self.middleware.call('system.general.ui_v6address_choices')

        ip4_addresses = data.get('ui_address')
        for ip4_address in ip4_addresses:
            if ip4_address not in ip4_addresses_list:
                verrors.add(
                    f'{schema}.ui_address',
                    f'{ip4_address} ipv4 address is not associated with this machine'
                )

        ip6_addresses = data.get('ui_v6address')
        for ip6_address in ip6_addresses:
            if ip6_address not in ip6_addresses_list:
                verrors.add(
                    f'{schema}.ui_v6address',
                    f'{ip6_address} ipv6 address is not associated with this machine'
                )

        for key, wildcard, ips in [('ui_address', '0.0.0.0', ip4_addresses), ('ui_v6address', '::', ip6_addresses)]:
            if wildcard in ips and len(ips) > 1:
                verrors.add(
                    f'{schema}.{key}',
                    f'When "{wildcard}" has been selected, selection of other addresses is not allowed'
                )

        certificate_id = data.get('ui_certificate')
        cert = await self.middleware.call(
            'certificate.query',
            [["id", "=", certificate_id]]
        )
        if not cert:
            verrors.add(
                f'{schema}.ui_certificate',
                'Please specify a valid certificate which exists in the system'
            )
        else:
            cert = cert[0]
            verrors.extend(
                await self.middleware.call(
                    'certificate.cert_services_validation', certificate_id, f'{schema}.ui_certificate', False
                )
            )

            if cert['fingerprint']:
                syslog.openlog(logoption=syslog.LOG_PID, facility=syslog.LOG_USER)
                syslog.syslog(syslog.LOG_ERR, 'Fingerprint of the certificate used in UI : ' + cert['fingerprint'])
                syslog.closelog()

        return verrors

    @accepts(
        Patch(
            'system_general_entry', 'general_settings',
            ('rm', {'name': 'crash_reporting_is_set'}),
            ('rm', {'name': 'usage_collection_is_set'}),
            ('rm', {'name': 'wizardshown'}),
            ('rm', {'name': 'id'}),
            ('replace', Int('ui_certificate', null=True)),
            ('add', Int('rollback_timeout', null=True)),
            ('add', Int('ui_restart_delay', null=True)),
            ('attr', {'update': True}),
        ),
    )
    async def do_update(self, data):
        """
        Update System General Service Configuration.

        `ui_certificate` is used to enable HTTPS access to the system. If `ui_certificate` is not configured on boot,
        it is automatically created by the system.

        `ui_httpsredirect` when set, makes sure that all HTTP requests are converted to HTTPS requests to better
        enhance security.

        `ui_address` and `ui_v6address` are a list of valid ipv4/ipv6 addresses respectively which the system will
        listen on.

        `ui_allowlist` is a list of IP addresses and networks that are allow to use API and UI. If this list is empty,
        then all IP addresses are allowed to use API and UI.

        `ds_auth` controls whether configured Directory Service users that are granted with Privileges are allowed to
        log in to the Web UI or use TrueNAS API.

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
        if not config.pop('crash_reporting_is_set'):
            config['crash_reporting'] = None
        if not config.pop('usage_collection_is_set'):
            config['usage_collection'] = None
        new_config = config.copy()
        new_config.update(data)

        verrors = await self.validate_general_settings(new_config, 'general_settings_update')
        if verrors:
            raise verrors

        keys = new_config.keys()
        for key in list(keys):
            if key.startswith('ui_'):
                new_config['gui' + key[3:]] = new_config.pop(key)

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            config['id'],
            new_config,
            {'prefix': 'stg_'}
        )

        if config['kbdmap'] != new_config['kbdmap']:
            await self.middleware.call('etc.generate', 'keyboard')
            await run(['setupcon'], check=False)
            await run(['localectl', 'set-keymap', new_config['kbdmap']], check=False)

        if config['timezone'] != new_config['timezone']:
            await self.middleware.call('zettarepl.update_config', {'timezone': new_config['timezone']})
            await self.middleware.call('service.reload', 'timeservices')
            await self.middleware.call('service.restart', 'cron')

        if config['language'] != new_config['language']:
            await self.middleware.call('system.general.set_language')

        if config['crash_reporting'] != new_config['crash_reporting']:
            await self.middleware.call('system.general.set_crash_reporting')

        await self.middleware.call('service.start', 'ssl')

        if rollback_timeout is not None:
            self._original_datastore = original_datastore
            self._rollback_timer = asyncio.get_event_loop().call_later(
                rollback_timeout,
                lambda: asyncio.ensure_future(self.rollback()),
            )

        if ui_restart_delay is not None:
            await self.middleware.call('system.general.ui_restart', ui_restart_delay)

        return await self.config()

    @private
    def set_crash_reporting(self):
        CrashReporting.enabled_in_settings = self.middleware.call_sync('system.general.config')['crash_reporting']

    @accepts()
    @returns(Int('remaining_seconds', null=True))
    async def checkin_waiting(self):
        """
        Determines whether or not we are waiting user to check-in the applied UI settings changes before they are rolled
        back. Returns a number of seconds before the automatic rollback or null if there are no changes pending.
        """
        if self._rollback_timer:
            remaining = self._rollback_timer.when() - asyncio.get_event_loop().time()
            if remaining > 0:
                return int(remaining)

    @accepts()
    @returns()
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
