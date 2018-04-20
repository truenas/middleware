from datetime import datetime
from middlewared.schema import accepts, Bool, Dict, Int, IPAddr, Str
from middlewared.service import ConfigService, no_auth_required, job, private, Service, ValidationErrors
from middlewared.utils import Popen, sw_version
from middlewared.validators import Range

import os
import re
import socket
import struct
import subprocess
import sys
import sysctl
import syslog
import time

from licenselib.license import ContractType

# FIXME: Temporary imports until debug lives in middlewared
if '/usr/local/www' not in sys.path:
    sys.path.append('/usr/local/www')
from freenasUI.support.utils import get_license
from freenasUI.system.utils import debug_get_settings, debug_run

# Flag telling whether the system completed boot and is ready to use
SYSTEM_READY = False


class SytemAdvancedService(ConfigService):

    class Config:
        datastore = 'system.advanced'
        datastore_prefix = 'adv_'
        datastore_extend = 'system.advanced.system_advanced_extend'
        namespace = 'system.advanced'

    @accepts()
    async def serial_port_choices(self):
        if(
            not await self.middleware.call('system.is_freenas') and
            await self.middleware.call('notifier.failover_hardware') == 'ECHOSTREAM'
        ):
            ports = ['0x3f8']
        else:
            pipe = await Popen("/usr/sbin/devinfo -u | grep -A 99999 '^I/O ports:' | "
                               "sed -En 's/ *([0-9a-fA-Fx]+).*\(uart[0-9]+\)/\\1/p'", stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, shell=True)
            ports = [y for y in (await pipe.communicate())[0].decode().strip().strip('\n').split('\n') if y]
            if not ports:
                ports = ['0x2f8']

        return ports

    async def system_advanced_extend(self, data):
        if data.get('sed_user'):
            data['sed_user'] = data.get('sed_user').upper()
        return data

    async def validate_fields(self, schema, data):
        verrors = ValidationErrors()

        user = data.get('periodic_notifyuser')
        if user:
            if not (
                await self.middleware.call(
                    'notifier.get_user_object',
                    user
                )
            ):
                verrors.add(
                    f'{schema}.periodic_notifyuser',
                    'Specified user does not exist'
                )

        serial_choice = data.get('serialport')
        if serial_choice:
            if serial_choice not in await self.serial_port_choices():
                verrors.add(
                    f'{schema}.serialport',
                    'Serial port specified has not been identified by the system'
                )
        return verrors, data

    @accepts(
        Dict(
            'system_advanced_update',
            Bool('advancedmode'),
            Bool('autotune'),
            Bool('consolemenu'),
            Bool('consolemsg'),
            Bool('consolescreensaver'),
            Bool('cpu_in_percentage'),
            Bool('debugkernel'),
            Bool('fqdn_syslog'),
            Str('graphite'),
            Str('motd'),
            Str('periodic_notifyuser'),
            Bool('powerdaemon'),
            Bool('serialconsole'),
            Str('serialport'),
            Str('serialspeed', enum=['9600', '19200', '38400', '57600', '115200']),
            Int('swapondrive', validators=[Range(min=0)]),
            Bool('traceback'),
            Bool('uploadcrash'),
            Bool('anonstats'),
            Str('sed_user', enum=['USER', 'MASTER'])
        )
    )
    async def do_update(self, data):
        config_data = await self.config()
        original_data = config_data.copy()
        config_data.update(data)

        verrors, config_data = await self.validate_fields('advanced_settings_update', config_data)
        if verrors:
            raise verrors

        if len(set(config_data.items()) ^ set(original_data.items())) > 0:
            if original_data.get('sed_user'):
                original_data['sed_user'] = original_data['sed_user'].lower()
            if config_data.get('sed_user'):
                config_data['sed_user'] = config_data['sed_user'].lower()

            await self.middleware.call(
                'datastore.update',
                self._config.datastore,
                config_data['id'],
                config_data,
                {'prefix': self._config.datastore_prefix}
            )

            loader_reloaded = False
            if original_data['motd'] != config_data['motd']:
                await self.middleware.call('service.start', 'motd', {'onetime': False})

            if original_data['consolemenu'] != config_data['consolemenu']:
                await self.middleware.call('service.start', 'ttys', {'onetime': False})

            if original_data['powerdaemon'] != config_data['powerdaemon']:
                await self.middleware.call('service.restart', 'powerd', {'onetime': False})

            if original_data['serialconsole'] != config_data['serialconsole']:
                await self.middleware.call('service.start', 'ttys', {'onetime': False})
                if not loader_reloaded:
                    await self.middleware.call('service.reload', 'loader', {'onetime': False})
                    loader_reloaded = True
            elif (
                    original_data['serialspeed'] != config_data['serialspeed'] or
                    original_data['serialport'] != config_data['serialport']
            ):
                if not loader_reloaded:
                    await self.middleware.call('service.reload', 'loader', {'onetime': False})
                    loader_reloaded = True

            if original_data['consolescreensaver'] != config_data['consolescreensaver']:
                if config_data['consolescreensaver'] == 0:
                    await self.middleware.call('service.stop', 'saver', {'onetime': False})
                else:
                    await self.middleware.call('service.start', 'saver', {'onetime': False})
                if not loader_reloaded:
                    await self.middleware.call('service.reload', 'loader', {'onetime': False})
                    loader_reloaded = True

            if (
                original_data['autotune'] != config_data['autotune'] and
                not loader_reloaded
            ):
                await self.middleware.call('service.reload', 'loader', {'onetime': False})
                loader_reloaded = True

            if (
                original_data['debugkernel'] != config_data['debugkernel'] and
                not loader_reloaded
            ):
                await self.middleware.call('service.reload', 'loader', {'onetime': False})

            if original_data['periodic_notifyuser'] != config_data['periodic_notifyuser']:
                await self.middleware.call('service.start', 'ix-periodic', {'onetime': False})

            if (
                original_data['cpu_in_percentage'] != config_data['cpu_in_percentage'] or
                original_data['graphite'] != config_data['graphite']
            ):
                await self.middleware.call('service.restart', 'collectd', {'onetime': False})

            if original_data['fqdn_syslog'] != config_data['fqdn_syslog']:
                await self.middleware.call('service.restart', 'syslogd', {'onetime': False})

        return await self.config()


class SystemService(Service):

    @no_auth_required
    @accepts()
    async def is_freenas(self):
        """
        Returns `true` if running system is a FreeNAS or `false` is Something Else.
        """
        # This is a stub calling notifier until we have all infrastructure
        # to implement in middlewared
        return await self.middleware.call('notifier.is_freenas')

    @accepts()
    def version(self):
        return sw_version()

    @accepts()
    def ready(self):
        """
        Returns whether the system completed boot and is ready to use
        """
        return SYSTEM_READY

    @accepts()
    async def info(self):
        """
        Returns basic system information.
        """
        uptime = (await (await Popen(
            "env -u TZ uptime | awk -F', load averages:' '{ print $1 }'",
            stdout=subprocess.PIPE,
            shell=True,
        )).communicate())[0].decode().strip()

        serial = await self._system_serial()

        product = (await(await Popen(
            ['dmidecode', '-s', 'system-product-name'],
            stdout=subprocess.PIPE,
        )).communicate())[0].decode().strip() or None

        manufacturer = (await(await Popen(
            ['dmidecode', '-s', 'system-manufacturer'],
            stdout=subprocess.PIPE,
        )).communicate())[0].decode().strip() or None

        license = get_license()[0]
        if license:
            license = {
                "system_serial": license.system_serial,
                "system_serial_ha": license.system_serial_ha,
                "contract_type": ContractType(license.contract_type).name.upper(),
                "contract_end": license.contract_end,
            }

        return {
            'version': self.version(),
            'hostname': socket.gethostname(),
            'physmem': sysctl.filter('hw.physmem')[0].value,
            'model': sysctl.filter('hw.model')[0].value,
            'cores': sysctl.filter('hw.ncpu')[0].value,
            'loadavg': os.getloadavg(),
            'uptime': uptime,
            'uptime_seconds': time.clock_gettime(5),  # CLOCK_UPTIME = 5
            'system_serial': serial,
            'system_product': product,
            'license': license,
            'boottime': datetime.fromtimestamp(
                struct.unpack('l', sysctl.filter('kern.boottime')[0].value[:8])[0]
            ),
            'datetime': datetime.utcnow(),
            'timezone': (await self.middleware.call('datastore.config', 'system.settings'))['stg_timezone'],
            'system_manufacturer': manufacturer,
        }

    @private
    async def _system_serial(self):
        return (await(await Popen(
            ['dmidecode', '-s', 'system-serial-number'],
            stdout=subprocess.PIPE,
        )).communicate())[0].decode().strip() or None

    @accepts(Dict('system-reboot', Int('delay', required=False), required=False))
    @job()
    async def reboot(self, job, options=None):
        """
        Reboots the operating system.

        Emits an "added" event of name "system" and id "reboot".
        """
        if options is None:
            options = {}

        self.middleware.send_event('system', 'ADDED', id='reboot', fields={
            'description': 'System is going to reboot',
        })

        delay = options.get('delay')
        if delay:
            time.sleep(delay)

        await Popen(["/sbin/reboot"])

    @accepts(Dict('system-shutdown', Int('delay', required=False), required=False))
    @job()
    async def shutdown(self, job, options=None):
        """
        Shuts down the operating system.

        Emits an "added" event of name "system" and id "shutdown".
        """
        if options is None:
            options = {}

        self.middleware.send_event('system', 'ADDED', id='shutdown', fields={
            'description': 'System is going to shutdown',
        })

        delay = options.get('delay')
        if delay:
            time.sleep(delay)

        await Popen(["/sbin/poweroff"])

    @accepts()
    @job(lock='systemdebug')
    def debug(self, job):
        # FIXME: move the implementation from freenasUI
        mntpt, direc, dump = debug_get_settings()
        debug_run(direc)
        return dump


class SystemGeneralService(ConfigService):

    class Config:
        namespace = 'system.general'
        datastore = 'system.settings'
        datastore_prefix = 'stg_'
        datastore_extend = 'system.general.general_system_extend'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._languages = self._initialize_system_languages()
        self._time_zones_list = None
        self._kbdmap_choices = None

    @private
    def general_system_extend(self, data):
        keys = data.keys()
        for key in keys:
            if key.startswith('gui'):
                data['ui_' + key[3:]] = data.pop(key)

        data['sysloglevel'] = data['sysloglevel'].upper()
        data['sysloglevel'] = data['sysloglevel'].upper()
        data['ui_certificate'] = data['ui_certificate']['id'] if data['ui_certificate'] else None
        return data

    @accepts()
    def get_system_languages(self):
        return self._languages

    def _initialize_system_languages(self):
        languagues = [
            ('af', 'Afrikaans'),
            ('ar', 'Arabic'),
            ('ast', 'Asturian'),
            ('az', 'Azerbaijani'),
            ('bg', 'Bulgarian'),
            ('be', 'Belarusian'),
            ('bn', 'Bengali'),
            ('br', 'Breton'),
            ('bs', 'Bosnian'),
            ('ca', 'Catalan'),
            ('cs', 'Czech'),
            ('cy', 'Welsh'),
            ('da', 'Danish'),
            ('de', 'German'),
            ('dsb', 'Lower Sorbian'),
            ('el', 'Greek'),
            ('en', 'English'),
            ('en-au', 'Australian English'),
            ('en-gb', 'British English'),
            ('eo', 'Esperanto'),
            ('es', 'Spanish'),
            ('es-ar', 'Argentinian Spanish'),
            ('es-co', 'Colombian Spanish'),
            ('es-mx', 'Mexican Spanish'),
            ('es-ni', 'Nicaraguan Spanish'),
            ('es-ve', 'Venezuelan Spanish'),
            ('et', 'Estonian'),
            ('eu', 'Basque'),
            ('fa', 'Persian'),
            ('fi', 'Finnish'),
            ('fr', 'French'),
            ('fy', 'Frisian'),
            ('ga', 'Irish'),
            ('gd', 'Scottish Gaelic'),
            ('gl', 'Galician'),
            ('he', 'Hebrew'),
            ('hi', 'Hindi'),
            ('hr', 'Croatian'),
            ('hsb', 'Upper Sorbian'),
            ('hu', 'Hungarian'),
            ('ia', 'Interlingua'),
            ('id', 'Indonesian'),
            ('io', 'Ido'),
            ('is', 'Icelandic'),
            ('it', 'Italian'),
            ('ja', 'Japanese'),
            ('ka', 'Georgian'),
            ('kab', 'Kabyle'),
            ('kk', 'Kazakh'),
            ('km', 'Khmer'),
            ('kn', 'Kannada'),
            ('ko', 'Korean'),
            ('lb', 'Luxembourgish'),
            ('lt', 'Lithuanian'),
            ('lv', 'Latvian'),
            ('mk', 'Macedonian'),
            ('ml', 'Malayalam'),
            ('mn', 'Mongolian'),
            ('mr', 'Marathi'),
            ('my', 'Burmese'),
            ('nb', 'Norwegian Bokmål'),
            ('ne', 'Nepali'),
            ('nl', 'Dutch'),
            ('nn', 'Norwegian Nynorsk'),
            ('os', 'Ossetic'),
            ('pa', 'Punjabi'),
            ('pl', 'Polish'),
            ('pt', 'Portuguese'),
            ('pt-br', 'Brazilian Portuguese'),
            ('ro', 'Romanian'),
            ('ru', 'Russian'),
            ('sk', 'Slovak'),
            ('sl', 'Slovenian'),
            ('sq', 'Albanian'),
            ('sr', 'Serbian'),
            ('sr-latn', 'Serbian Latin'),
            ('sv', 'Swedish'),
            ('sw', 'Swahili'),
            ('ta', 'Tamil'),
            ('te', 'Telugu'),
            ('th', 'Thai'),
            ('tr', 'Turkish'),
            ('tt', 'Tatar'),
            ('udm', 'Udmurt'),
            ('uk', 'Ukrainian'),
            ('ur', 'Urdu'),
            ('vi', 'Vietnamese'),
            ('zh-hans', 'Simplified Chinese'),
            ('zh-hant', 'Traditional Chinese'),
        ]
        return dict(languagues)

    async def _initialize_timezones_list(self):
        pipe = await Popen(
            'find /usr/share/zoneinfo/ -type f -not -name zone.tab -not -regex \'.*/Etc/GMT.*\'',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True
        )
        self._time_zones_list = (await pipe.communicate())[0].decode().strip().split('\n')
        self._time_zones_list = [x[20:] for x in self._time_zones_list]
        self._time_zones_list.sort()

    @accepts()
    async def get_timezones(self):
        if not self._time_zones_list:
            await self._initialize_timezones_list()
        return self._time_zones_list

    async def _initialize_kbdmap_choices(self):
        """Populate choices from /usr/share/vt/keymaps/INDEX.keymaps"""
        index = "/usr/share/vt/keymaps/INDEX.keymaps"

        if not os.path.exists(index):
            return []
        with open(index, 'rb') as f:
            d = f.read().decode('utf8', 'ignore')
        _all = re.findall(r'^(?P<name>[^#\s]+?)\.kbd:en:(?P<desc>.+)$', d, re.M)
        self._kbdmap_choices = [(name, desc) for name, desc in _all]

    @accepts()
    async def get_kbdmap_choices(self):
        if not self._kbdmap_choices:
            await self._initialize_kbdmap_choices()
        return self._kbdmap_choices

    async def validate_general_settings(self, data, schema):
        verrors = ValidationErrors()

        language = data.get('language')
        if language:
            system_languages = self.get_system_languages()
            if language not in system_languages.keys():
                verrors.add(
                    f'{schema}.language',
                    f'Specified "{language}" language not found, kindly correct it'
                )

        # kbd map needs work

        timezone = data.get('timezone')
        if timezone:
            timezones = await self.get_timezones()
            if timezone not in timezones:
                verrors.add(
                    f'{schema}.timezone',
                    'Please select a correct timezone'
                )

        ip_addresses = await self.middleware.call(
            'interfaces.ip_in_use'
        )
        ip4_addresses_list = [alias_dict['address'] for alias_dict in ip_addresses if alias_dict['type'] == 'INET']
        ip6_addresses_list = [alias_dict['address'] for alias_dict in ip_addresses if alias_dict['type'] == 'INET6']

        ip4_address = data.get('ui_address')
        if (
            ip4_address and
            ip4_address != '0.0.0.0' and
            ip4_address not in ip4_addresses_list
        ):
            verrors.add(
                f'{schema}.ui_address',
                'Selected ipv4 address is not associated with this machine'
            )

        ip6_address = data.get('ui_v6address')
        if (
            ip6_address and
            ip6_address != '::' and
            ip6_address not in ip6_addresses_list
        ):
            verrors.add(
                f'{schema}.ui_v6address',
                'Selected ipv6 address is not associated with this machine'
            )

        syslog_server = data.get('syslogserver')
        if syslog_server:
            match = re.match("^[\w\.\-]+(\:\d+)?$", syslog_server)
            if not match:
                verrors.add(
                    f'{schema}.syslogserver',
                    'Invalid syslog server format'
                )
            elif ':' in syslog_server:
                port = int(syslog_server.split(':')[-1])
                if port < 0 or port > 65535:
                    verrors.add(
                        f'{schema}.syslogserver',
                        'Port specified should be between 0 - 65535'
                    )

        protocol = data.get('ui_protocol')
        if protocol:
            if protocol != 'HTTP':
                certificate_id = data.get('ui_certificate')
                if not certificate_id:
                    verrors.add(
                        f'{schema}.ui_certificate',
                        'Protocol has been selected as HTTPS, certificate is required'
                    )
                else:
                    # getting fingerprint for certificate
                    fingerprint = await self.middleware.call(
                        'certificate.get_fingerprint',
                        certificate_id
                    )
                    if fingerprint:
                        syslog.openlog(logoption=syslog.LOG_PID, facility=syslog.LOG_USER)
                        syslog.syslog(syslog.LOG_ERR, 'Fingerprint of the certificate used in UI : ' + fingerprint)
                        syslog.closelog()
                    else:
                        # Two reasons value is None - certificate not found - error while parsing the certificate for
                        # fingerprint
                        verrors.add(
                            f'{schema}.ui_certificate',
                            'Kindly check if the certificate has been added to the system and it is a valid certificate'
                        )
        return verrors

    @accepts(
        Dict(
            'general_settings',
            IPAddr('ui_address'),
            Int('ui_certificate'),
            Int('ui_httpsport', validators=[Range(min=1, max=65535)]),
            Bool('ui_httpsredirect'),
            Int('ui_port', validators=[Range(min=1, max=65535)]),
            Str('ui_protocol', enum=['HTTP', 'HTTPS', 'HTTPHTTPS']),
            IPAddr('ui_v6address'),
            Str('kbdmap'),
            Str('language'),
            Str('sysloglevel', enum=['F_EMERG', 'F_ALERT', 'F_CRIT', 'F_ERR', 'F_WARNING', 'F_NOTICE',
                                     'F_INFO', 'F_DEBUG', 'F_IS_DEBUG']),
            Str('syslogserver'),
            Str('timezone')
        )
    )
    async def do_update(self, data):
        config = await self.config()
        new_config = config.copy()
        new_config.update(data)
        verrors = await self.validate_general_settings(new_config, 'general_settings_update')
        if verrors:
            raise verrors

        if len(set(new_config.items()) ^ set(config.items())) > 0:
            # Converting new_config to map the database table fields
            new_config['sysloglevel'] = new_config['sysloglevel'].lower()
            new_config['ui_protocol'] = new_config['ui_protocol'].lower()
            keys = new_config.keys()
            for key in keys:
                if key.startswith('ui_'):
                    new_config['gui' + key[3:]] = new_config.pop(key)

            await self.middleware.call(
                'datastore.update',
                self._config.datastore,
                config['id'],
                new_config,
                {'prefix': 'stg_'}
            )

            # case insensitive comparison should be performed for sysloglevel
            if (
                config['sysloglevel'].lower() != new_config['sysloglevel'].lower() or
                    config['syslogserver'] != new_config['syslogserver']
            ):
                await self.middleware.call('service.restart', 'syslogd')

            if config['timezone'] != new_config['timezone']:
                await self.middleware.call('service.reload', 'timeservices')
                await self.middleware.call('service.restart', 'cron')

            await self.middleware.call('service._start_ssl', 'nginx')
        return await self.config()


async def _event_system_ready(middleware, event_type, args):
    """
    Method called when system is ready, supposed to enable the flag
    telling the system has completed boot.
    """
    global SYSTEM_READY
    if args['id'] == 'ready':
        SYSTEM_READY = True


def setup(middleware):
    middleware.event_subscribe('system', _event_system_ready)
