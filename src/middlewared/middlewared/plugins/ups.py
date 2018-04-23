import csv
import glob
import io
import os
import re

from middlewared.schema import accepts, Bool, Dict, Int, List, Str
from middlewared.service import private, SystemServiceService, ValidationErrors
from middlewared.validators import Email


DRIVER_BIN_DIR = '/usr/local/libexec/nut'


class UPSService(SystemServiceService):
    DRIVERS_AVAILABLE = set(os.listdir(DRIVER_BIN_DIR))

    class Config:
        datastore = 'services.ups'
        datastore_prefix = 'ups_'
        datastore_extend = 'ups.ups_config_extend'
        service = 'ups'
        service_verb = 'restart'

    @private
    async def ups_config_extend(self, data):
        data['mode'] = data['mode'].upper()
        data['shutdown'] = data['shutdown'].upper()
        data['toemail'] = [v for v in data['toemail'].split(';') if v]
        return data

    @accepts()
    async def port_choices(self):
        ports = [x for x in glob.glob('/dev/cua*') if x.find('.') == -1]
        ports.extend(glob.glob('/dev/ugen*'))
        ports.extend(glob.glob('/dev/uhid*'))
        return ports

    @accepts()
    def driver_choices(self):
        ups_choices = {}
        if os.path.exists("/conf/base/etc/local/nut/driver.list"):
            with open('/conf/base/etc/local/nut/driver.list', 'rb') as f:
                d = f.read().decode('utf8', 'ignore')
            r = io.StringIO()
            for line in re.sub(r'[ \t]+', ' ', d, flags=re.M).split('\n'):
                r.write(line.strip() + '\n')
            r.seek(0)
            reader = csv.reader(r, delimiter=' ', quotechar='"')
            for row in reader:
                if len(row) == 0 or row[0].startswith('#'):
                    continue
                if row[-2] == '#':
                    last = -3
                else:
                    last = -1
                driver = row[last].split()[0]
                if driver not in self.DRIVERS_AVAILABLE:
                    continue
                if row[last].find(' (experimental)') != -1:
                    row[last] = row[last].replace(' (experimental)', '').strip()
                for i, field in enumerate(list(row)):
                    row[i] = field
                ups_choices['$'.join([row[last], row[3]])] = '%s (%s)' % (' '.join(row[0:last]), row[last])
        return ups_choices

    @private
    async def validate_data(self, data, schema):
        verrors = ValidationErrors()

        driver = data.get('driver')
        if driver:
            if driver not in (await self.middleware.call('ups.driver_choices')).keys():
                verrors.add(
                    f'{schema}.driver',
                    'Driver selected does not match local machine\'s driver list'
                )

        identifier = data['identifier']
        if identifier:
            if not re.search(r'^[a-z0-9\.\-_]+$', identifier, re.I):
                verrors.add(
                    f'{schema}.identifier',
                    'Use alphanumeric characters, ".", "-" and "_"'
                )

        for field in [field for field in ['monpwd', 'monuser'] if data.get(field)]:
            if re.search(r'[ #]', data[field], re.I):
                verrors.add(
                    f'{schema}.{field}',
                    'Spaces or number signs are not allowed'
                )

        mode = data.get('mode')
        if mode:
            if mode == 'MASTER':
                if not data.get('port'):
                    verrors.add(
                        f'{schema}.port',
                        'This field is required'
                    )
            else:
                if not data.get('remotehost'):
                    verrors.add(
                        f'{schema}.remotehost',
                        'This field is required'
                    )

        to_emails = data.get('toemail')
        if to_emails:
            data['toemail'] = ';'.join(to_emails)
        else:
            data['toemail'] = ''

        data['mode'] = data['mode'].lower()
        data['shutdown'] = data['shutdown'].lower()

        return verrors, data

    @accepts(
        Dict(
            'ups_update',
            Bool('emailnotify'),
            Bool('powerdown'),
            Bool('rmonitor'),
            Int('nocommwarntime'),
            Int('remoteport'),
            Int('shutdowntimer'),
            Str('description'),
            Str('driver'),
            Str('extrausers'),
            Str('identifier'),
            Str('mode', enum=['MASTER', 'SLAVE']),
            Str('monpwd'),
            Str('monuser'),
            Str('options'),
            Str('optionsupsd'),
            Str('port'),
            Str('remotehost'),
            Str('shutdown', enum=['LOWBATT', 'BATT']),
            Str('shutdowncmd'),
            Str('subject'),
            List('toemail', items=[Str('email', validators=[Email()])]),
        )
    )
    async def do_update(self, data):
        config = await self.config()
        old_config = config.copy()
        config.update(data)
        verros, config = await self.validate_data(config, 'ups_update')
        if verros:
            raise verros

        old_config['mode'] = old_config['mode'].lower()
        old_config['shutdown'] = old_config['shutdown'].lower()
        old_config['toemail'] = ';'.join(old_config['toemail']) if old_config['toemail'] else ''

        if len(set(old_config.items()) ^ set(config.items())) > 0:
            await self._update_service(old_config, config)

        return await self.config()
