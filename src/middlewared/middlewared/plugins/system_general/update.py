import syslog
import warnings

import middlewared.sqlalchemy as sa

from middlewared.logger import CrashReporting
from middlewared.schema import accepts, Bool, Datetime, Dict, Int, IPAddr, List, Patch, Str
from middlewared.service import ConfigService, private, ValidationErrors
from middlewared.validators import Range

from .utils import HTTPS_PROTOCOLS


class SystemGeneralModel(sa.Model):
    __tablename__ = 'system_settings'

    id = sa.Column(sa.Integer(), primary_key=True)
    stg_guiaddress = sa.Column(sa.JSON(type=list), default=['0.0.0.0'])
    stg_guiv6address = sa.Column(sa.JSON(type=list), default=['::'])
    stg_guiport = sa.Column(sa.Integer(), default=80)
    stg_guihttpsport = sa.Column(sa.Integer(), default=443)
    stg_guihttpsredirect = sa.Column(sa.Boolean(), default=False)
    stg_guix_frame_options = sa.Column(sa.String(120), default='SAMEORIGIN')
    stg_language = sa.Column(sa.String(120), default='en')
    stg_kbdmap = sa.Column(sa.String(120))
    stg_birthday = sa.Column(sa.DateTime(), nullable=True)
    stg_timezone = sa.Column(sa.String(120), default='America/Los_Angeles')
    stg_wizardshown = sa.Column(sa.Boolean(), default=False)
    stg_pwenc_check = sa.Column(sa.String(100))
    stg_guicertificate_id = sa.Column(sa.ForeignKey('system_certificate.id'), index=True, nullable=True)
    stg_crash_reporting = sa.Column(sa.Boolean(), nullable=True)
    stg_usage_collection = sa.Column(sa.Boolean(), nullable=True)
    stg_guihttpsprotocols = sa.Column(sa.JSON(type=list), default=['TLSv1', 'TLSv1.1', 'TLSv1.2', 'TLSv1.3'])
    stg_guiconsolemsg = sa.Column(sa.Boolean(), default=True)


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
        Int('id', required=True),
    )

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

        language = data.get('language')
        system_languages = await self.middleware.call('system.general.language_choices')
        if language not in system_languages.keys():
            verrors.add(
                f'{schema}.language',
                f'Specified "{language}" language unknown. Please select a valid language.'
            )

        # kbd map needs work

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
            ('add', Str(
                'sysloglevel', enum=[
                    'F_EMERG', 'F_ALERT', 'F_CRIT', 'F_ERR', 'F_WARNING', 'F_NOTICE', 'F_INFO', 'F_DEBUG',
                ]
            )),
            ('add', Str('syslogserver')),
            ('rm', {'name': 'crash_reporting_is_set'}),
            ('rm', {'name': 'usage_collection_is_set'}),
            ('rm', {'name': 'wizardshown'}),
            ('rm', {'name': 'id'}),
            ('replace', Int('ui_certificate', null=True)),
            ('attr', {'update': True}),
        )
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

        `syslogserver` and `sysloglevel` are deprecated fields as of 11.3
        and will be permanently moved to system.advanced.update for 12.0
        """
        advanced_config = {}
        # fields were moved to Advanced
        for deprecated_field in ('sysloglevel', 'syslogserver'):
            if deprecated_field in data:
                warnings.warn(
                    f"{deprecated_field} has been deprecated and moved to 'system.advanced'",
                    DeprecationWarning
                )
                advanced_config[deprecated_field] = data[deprecated_field]
                del data[deprecated_field]
        if advanced_config:
            await self.middleware.call('system.advanced.update', advanced_config)

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
            await self.middleware.call('service.restart', 'syscons')

        if config['timezone'] != new_config['timezone']:
            await self.middleware.call('zettarepl.update_config', {'timezone': new_config['timezone']})
            await self.middleware.call('service.reload', 'timeservices')
            await self.middleware.call('service.restart', 'cron')

        if config['language'] != new_config['language']:
            await self.middleware.call('system.general.set_language')

        if config['crash_reporting'] != new_config['crash_reporting']:
            await self.middleware.call('system.general.set_crash_reporting')

        await self.middleware.call('service.start', 'ssl')

        return await self.config()

    @private
    def set_crash_reporting(self):
        CrashReporting.enabled_in_settings = self.middleware.call_sync('system.general.config')['crash_reporting']
