from datetime import datetime, date
from middlewared.event import EventSource
from middlewared.schema import accepts, Bool, Dict, Int, IPAddr, List, Str
from middlewared.service import ConfigService, no_auth_required, job, private, Service, ValidationErrors
from middlewared.utils import Popen, start_daemon_thread, sw_buildtime, sw_version
from middlewared.validators import Range

import csv
import os
import psutil
import re
import socket
import struct
import subprocess
import sys
import sysctl
import syslog
import time

from licenselib.license import ContractType, Features

# FIXME: Temporary imports until debug lives in middlewared
if '/usr/local/www' not in sys.path:
    sys.path.append('/usr/local/www')
from freenasUI.support.utils import get_license
from freenasUI.system.utils import debug_get_settings, debug_run

# Flag telling whether the system completed boot and is ready to use
SYSTEM_READY = False

CACHE_POOLS_STATUSES = 'system.system_health_pools'


class SytemAdvancedService(ConfigService):

    class Config:
        datastore = 'system.advanced'
        datastore_prefix = 'adv_'
        datastore_extend = 'system.advanced.system_advanced_extend'
        namespace = 'system.advanced'

    @accepts()
    async def serial_port_choices(self):
        """
        Get available choices for `serialport` attribute in `system.advanced.update`.
        """
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

    @private
    async def system_advanced_extend(self, data):

        if data.get('sed_user'):
            data['sed_user'] = data.get('sed_user').upper()

        return data

    async def __validate_fields(self, schema, data):
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
        if data.get('serialconsole'):

            if not serial_choice:
                verrors.add(
                    f'{schema}.serialport',
                    'Please specify a serial port when serial console option is checked'
                )
            elif serial_choice not in await self.serial_port_choices():
                verrors.add(
                    f'{schema}.serialport',
                    'Serial port specified has not been identified by the system'
                )

        elif not serial_choice:
            # TODO: THIS CHECK CAN BE REMOVED WHEN WE DISALLOW NONE VALUES IN THE SCHEMA LAYER

            verrors.add(
                f'{schema}.serialport',
                'Empty serial port is not allowed'
            )

        return verrors, data

    @accepts(
        Dict(
            'system_advanced_update',
            Bool('advancedmode'),
            Bool('autotune'),
            Bool('consolemenu'),
            Bool('consolemsg'),
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
            Str('sed_user', enum=['USER', 'MASTER']),
            Str('sed_passwd', password=True),
            update=True
        )
    )
    async def do_update(self, data):
        config_data = await self.config()
        original_data = config_data.copy()
        config_data.update(data)

        verrors, config_data = await self.__validate_fields('advanced_settings_update', config_data)
        if verrors:
            raise verrors

        if len(set(config_data.items()) ^ set(original_data.items())) > 0:
            if original_data.get('sed_user'):
                original_data['sed_user'] = original_data['sed_user'].lower()
            if config_data.get('sed_user'):
                config_data['sed_user'] = config_data['sed_user'].lower()

            # PASSWORD ENCRYPTION FOR SED IS BEING DONE IN THE MODEL ITSELF

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

    async def __get_license(self):
        licenseobj = get_license()[0]
        if not licenseobj:
            return
        license = {
            "system_serial": licenseobj.system_serial,
            "system_serial_ha": licenseobj.system_serial_ha,
            "contract_type": ContractType(licenseobj.contract_type).name.upper(),
            "contract_end": licenseobj.contract_end,
            "features": [],
        }
        for feature in licenseobj.features:
            license["features"].append(feature.name.upper())
        # Licenses issued before 2017-04-14 had a bug in the feature bit
        # for fibre channel, which means they were issued having
        # dedup+jails instead.
        if (
            licenseobj.contract_start < date(2017, 4, 14) and
            Features.dedup in licenseobj.features and
            Features.jails in licenseobj.features
        ):
            license["features"].append(Features.fibrechannel.name.upper())
        return license

    @accepts()
    async def info(self):
        """
        Returns basic system information.
        """
        buildtime = sw_buildtime()
        if buildtime:
            buildtime = datetime.fromtimestamp(int(buildtime)),

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

        return {
            'version': self.version(),
            'buildtime': buildtime,
            'hostname': socket.gethostname(),
            'physmem': sysctl.filter('hw.physmem')[0].value,
            'model': sysctl.filter('hw.model')[0].value,
            'cores': sysctl.filter('hw.ncpu')[0].value,
            'loadavg': os.getloadavg(),
            'uptime': uptime,
            'uptime_seconds': time.clock_gettime(5),  # CLOCK_UPTIME = 5
            'system_serial': serial,
            'system_product': product,
            'license': await self.__get_license(),
            'boottime': datetime.fromtimestamp(
                struct.unpack('l', sysctl.filter('kern.boottime')[0].value[:8])[0]
            ),
            'datetime': datetime.utcnow(),
            'timezone': (await self.middleware.call('datastore.config', 'system.settings'))['stg_timezone'],
            'system_manufacturer': manufacturer,
        }

    @accepts(Str('feature', enum=['DEDUP', 'FIBRECHANNEL', 'JAILS', 'VM']))
    async def feature_enabled(self, name):
        """
        Returns whether the `feature` is enabled or not
        """
        is_freenas = await self.middleware.call('system.is_freenas')
        if name == 'FIBRECHANNEL' and is_freenas:
            return False
        elif is_freenas:
            return True
        license = await self.__get_license()
        if license and name in license['features']:
            return True
        return False

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
        self._language_choices = self._initialize_languages()
        self._timezone_choices = None
        self._kbdmap_choices = None
        self._country_choices = {}

    @private
    def general_system_extend(self, data):
        keys = data.keys()
        for key in keys:
            if key.startswith('gui'):
                data['ui_' + key[3:]] = data.pop(key)

        data['sysloglevel'] = data['sysloglevel'].upper()
        data['sysloglevel'] = data['sysloglevel'].upper()
        data['ui_protocol'] = data['ui_protocol'].upper()
        data['ui_certificate'] = data['ui_certificate']['id'] if data['ui_certificate'] else None
        return data

    @accepts()
    def language_choices(self):
        return self._language_choices

    @private
    def _initialize_languages(self):
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

    @private
    async def _initialize_timezone_choices(self):
        pipe = await Popen(
            'find /usr/share/zoneinfo/ -type f -not -name zone.tab -not -regex \'.*/Etc/GMT.*\'',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True
        )
        self._timezone_choices = (await pipe.communicate())[0].decode().strip().split('\n')
        self._timezone_choices = {x[20:]: x[20:] for x in self._timezone_choices}

    @accepts()
    async def timezone_choices(self):
        if not self._timezone_choices:
            await self._initialize_timezone_choices()
        return self._timezone_choices

    @accepts()
    async def country_choices(self):
        if not self._country_choices:
            await self._initialize_country_choices()
        return self._country_choices

    @private
    async def _initialize_country_choices(self):

        def _get_index(country_columns, column):
            index = -1

            i = 0
            for c in country_columns:
                if c.lower() == column.lower():
                    index = i
                    break

                i += 1

            return index

        country_file = '/etc/iso_3166_2_countries.csv'
        cni, two_li = None, None
        with open(country_file, 'r', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)

            for index, row in enumerate(reader):
                if index != 0:
                    if row[cni] and row[two_li]:
                        if row[two_li] in self._country_choices:
                            # If two countries in the iso file have the same key, we concatenate their names
                            self._country_choices[row[two_li]] += f' + {row[cni]}'
                        else:
                            self._country_choices[row[two_li]] = row[cni]
                else:
                    # ONLY CNI AND TWO_LI ARE BEING CONSIDERED FROM THE CSV
                    cni = _get_index(row, 'Common Name')
                    two_li = _get_index(row, 'ISO 3166-1 2 Letter Code')

    @private
    async def _initialize_kbdmap_choices(self):
        """Populate choices from /usr/share/vt/keymaps/INDEX.keymaps"""
        index = "/usr/share/vt/keymaps/INDEX.keymaps"

        if not os.path.exists(index):
            return []
        with open(index, 'rb') as f:
            d = f.read().decode('utf8', 'ignore')
        _all = re.findall(r'^(?P<name>[^#\s]+?)\.kbd:en:(?P<desc>.+)$', d, re.M)
        self._kbdmap_choices = {name: desc for name, desc in _all}

    @accepts()
    async def kbdmap_choices(self):
        if not self._kbdmap_choices:
            await self._initialize_kbdmap_choices()
        return self._kbdmap_choices

    @private
    async def validate_general_settings(self, data, schema):
        verrors = ValidationErrors()

        language = data.get('language')
        if language:
            system_languages = self.language_choices()
            if language not in system_languages.keys():
                verrors.add(
                    f'{schema}.language',
                    f'Specified "{language}" language not found, kindly correct it'
                )

        # kbd map needs work

        timezone = data.get('timezone')
        if timezone:
            timezones = await self.timezone_choices()
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

        ip4_addresses = data.get('ui_address')
        for ip4_address in ip4_addresses:
            if (
                ip4_address and
                ip4_address != '0.0.0.0' and
                ip4_address not in ip4_addresses_list
            ):
                verrors.add(
                    f'{schema}.ui_address',
                    f'{ip4_address} ipv4 address is not associated with this machine'
                )

        ip6_addresses = data.get('ui_v6address')
        for ip6_address in ip6_addresses:
            if (
                ip6_address and
                ip6_address != '::' and
                ip6_address not in ip6_addresses_list
            ):
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
                    cert = await self.middleware.call(
                        'certificate.query',
                        [
                            ["id", "=", certificate_id],
                            ["CSR", "=", None]
                        ]
                    )
                    if not cert:
                        verrors.add(
                            f'{schema}.ui_certificate',
                            'Please specify a valid certificate which exists on the FreeNAS system'
                        )
                    else:
                        # getting fingerprint for certificate
                        fingerprint = await self.middleware.call(
                            'certificate.get_fingerprint_of_cert',
                            certificate_id
                        )
                        if fingerprint:
                            syslog.openlog(logoption=syslog.LOG_PID, facility=syslog.LOG_USER)
                            syslog.syslog(syslog.LOG_ERR, 'Fingerprint of the certificate used in UI : ' + fingerprint)
                            syslog.closelog()
                        else:
                            # Two reasons value is None - certificate not found - error while parsing the certificate
                            # for fingerprint
                            verrors.add(
                                f'{schema}.ui_certificate',
                                'Kindly check if the certificate has been added to the system and it is a '
                                'valid certificate'
                            )
        return verrors

    @accepts(
        Dict(
            'general_settings',
            Int('ui_certificate', null=True),
            Int('ui_httpsport', validators=[Range(min=1, max=65535)]),
            Bool('ui_httpsredirect'),
            Int('ui_port', validators=[Range(min=1, max=65535)]),
            Str('ui_protocol', enum=['HTTP', 'HTTPS', 'HTTPHTTPS']),
            List('ui_address', items=[IPAddr('addr')], empty=False),
            List('ui_v6address', items=[IPAddr('addr')], empty=False),
            Str('kbdmap'),
            Str('language'),
            Str('sysloglevel', enum=['F_EMERG', 'F_ALERT', 'F_CRIT', 'F_ERR', 'F_WARNING', 'F_NOTICE',
                                     'F_INFO', 'F_DEBUG', 'F_IS_DEBUG']),
            Str('syslogserver'),
            Str('timezone'),
            update=True,
        )
    )
    async def do_update(self, data):
        config = await self.config()
        new_config = config.copy()
        new_config.update(data)

        verrors = await self.validate_general_settings(new_config, 'general_settings_update')
        if verrors:
            raise verrors

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


async def _event_zfs_status(middleware, event_type, args):
    """
    This is so we can invalidate the CACHE_POOLS_STATUSES cache
    when pool status changes
    """
    data = args['data']
    if data.get('type') == 'misc.fs.zfs.vdev_statechange':
        await middleware.call('cache.pop', CACHE_POOLS_STATUSES)


class SystemHealthEventSource(EventSource):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._check_update = None
        start_daemon_thread(target=self.check_update)

    def check_update(self):
        while not self._cancel.is_set():
            self._check_update = self.middleware.call_sync('update.check_available')['status']
            self._cancel.wait(timeout=60 * 60 * 24)

    def pools_statuses(self):
        return {
            p['name']: {'status': p['status']}
            for p in self.middleware.call_sync('pool.query')
        }

    def run(self):

        try:
            if self.arg:
                delay = int(self.arg)
            else:
                delay = 10
        except ValueError:
            return

        # Delay too slow
        if delay < 5:
            return

        cp_time = sysctl.filter('kern.cp_time')[0].value
        cp_old = cp_time

        while not self._cancel.is_set():
            time.sleep(delay)

            cp_time = sysctl.filter('kern.cp_time')[0].value
            cp_diff = list(map(lambda x: x[0] - x[1], zip(cp_time, cp_old)))
            cp_old = cp_time

            cpu_percent = round((sum(cp_diff[:3]) / sum(cp_diff)) * 100, 2)

            pools = self.middleware.call_sync(
                'cache.get_or_put',
                CACHE_POOLS_STATUSES,
                1800,
                self.pools_statuses,
            )

            self.send_event('ADDED', fields={
                'cpu_percent': cpu_percent,
                'memory': psutil.virtual_memory()._asdict(),
                'pools': pools,
                'update': self._check_update,
            })


def setup(middleware):
    global SYSTEM_READY
    if os.path.exists("/tmp/.bootready"):
        SYSTEM_READY = True

    middleware.event_subscribe('system', _event_system_ready)
    middleware.event_subscribe('devd.zfs', _event_zfs_status)
    middleware.register_event_source('system.health', SystemHealthEventSource)
