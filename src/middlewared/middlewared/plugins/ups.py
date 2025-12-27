import csv
import functools
import glob
import io
import os
import re

from middlewared.api import api_method
from middlewared.api.current import (
    UPSEntry, UPSUpdateArgs, UPSUpdateResult, UPSPortChoicesArgs, UPSPortChoicesResult,
    UPSDriverChoicesArgs, UPSDriverChoicesResult,
)
from middlewared.service import private, SystemServiceService, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils import run
from middlewared.utils.serial import serial_port_choices


RE_DRIVER_CHOICE = re.compile(r'(\S+)\s+(\S+=\S+)?\s*(?:\((.+)\))?$')
RE_TEST_IN_PROGRESS = re.compile(r'ups.test.result:\s*TestInProgress')
RE_UPS_STATUS = re.compile(r'ups.status: (.*)')
UPS_POWERDOWN_FLAG_FILE = '/etc/killpower'


class UPSModel(sa.Model):
    __tablename__ = 'services_ups'

    id = sa.Column(sa.Integer(), primary_key=True)
    ups_mode = sa.Column(sa.String(6), default='master')
    ups_identifier = sa.Column(sa.String(120), default='ups')
    ups_remotehost = sa.Column(sa.String(50))
    ups_remoteport = sa.Column(sa.Integer(), default=3493)
    ups_driver = sa.Column(sa.String(120))
    ups_port = sa.Column(sa.String(120))
    ups_options = sa.Column(sa.Text())
    ups_optionsupsd = sa.Column(sa.Text())
    ups_description = sa.Column(sa.String(120))
    ups_shutdown = sa.Column(sa.String(120), default='batt')
    ups_shutdowntimer = sa.Column(sa.Integer(), default=30)
    ups_monuser = sa.Column(sa.String(50), default='upsmon')
    ups_monpwd = sa.Column(sa.EncryptedText(), default='fixmepass')
    ups_extrausers = sa.Column(sa.Text())
    ups_rmonitor = sa.Column(sa.Boolean(), default=False)
    ups_powerdown = sa.Column(sa.Boolean(), default=False)
    ups_nocommwarntime = sa.Column(sa.Integer(), nullable=True)
    ups_hostsync = sa.Column(sa.Integer(), default=15)
    ups_shutdowncmd = sa.Column(sa.String(255), nullable=True)


@functools.cache
def drivers_available():
    return set(os.listdir('/lib/nut'))


class UPSService(SystemServiceService):

    LOGGED_ERRORS = []

    class Config:
        datastore = 'services.ups'
        datastore_prefix = 'ups_'
        datastore_extend = 'ups.ups_config_extend'
        service = 'ups'
        service_verb = 'restart'
        cli_namespace = 'service.ups'
        role_prefix = 'SYSTEM_GENERAL'
        entry = UPSEntry

    @private
    async def ups_config_extend(self, data):
        data['mode'] = data['mode'].upper()
        data['shutdown'] = data['shutdown'].upper()
        if data['mode'] == 'SLAVE':
            # Slave mode: use dummy-ups repeater to connect to remote master
            data['driver'] = 'dummy-ups'
            data['port'] = f"{data['identifier']}@{data['remotehost']}:{data['remoteport']}"
        # Always use localhost since we run local NUT server (master or dummy-ups repeater)
        data['complete_identifier'] = f'{data["identifier"]}@localhost:{data["remoteport"]}'
        return data

    @api_method(UPSPortChoicesArgs, UPSPortChoicesResult, roles=['SYSTEM_GENERAL_READ'])
    async def port_choices(self):
        adv_config = await self.middleware.call('system.advanced.config')
        ports = [
            os.path.join('/dev', port['name'])
            for port in await self.middleware.run_in_thread(serial_port_choices)
            if not adv_config['serialconsole'] or adv_config['serialport'] != port['name']
        ]
        ports.extend(glob.glob('/dev/uhid*'))
        ports.append('auto')
        return ports

    @private
    def normalize_driver_string(self, driver_str):
        driver = driver_str.split('$')[0]
        driver = driver.split('(')[0]  # "blazer_usb (USB ID 0665:5161)"
        driver = driver.split(' or ')[0]  # "blazer_ser or blazer_usb"
        driver = driver.replace(' ', '\n\t')  # "genericups upstype=16"
        return f'driver = {driver}'

    @api_method(UPSDriverChoicesArgs, UPSDriverChoicesResult, roles=['SYSTEM_GENERAL_READ'])
    def driver_choices(self):
        """
        Returns choices of UPS drivers supported by the system.
        """
        ups_choices = {}
        driver_list = '/usr/share/nut/driver.list'
        if os.path.exists(driver_list):
            with open(driver_list, 'r') as f:
                d = f.read()
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
                driver_str = row[last]
                driver_options = ''
                driver_annotation = ''
                # We want to match following strings
                # genericups upstype=1
                # powerman-pdu (experimental)
                m = RE_DRIVER_CHOICE.match(driver_str)
                if m:
                    driver_str = m.group(1)
                    driver_options = m.group(2) or ''
                    driver_annotation = m.group(3) or ''
                for driver in driver_str.split(' or '):  # can be "blazer_ser or blazer_usb"
                    driver = driver.strip()
                    if driver not in drivers_available():
                        continue
                    for i, field in enumerate(list(row)):
                        row[i] = field
                    key = '$'.join([driver + (f' {driver_options}' if driver_options else ''), row[3]])
                    val = f'{ups_choices[key]} / ' if key in ups_choices else ''
                    ups_choices[key] = val + '%s (%s)' % (
                        ' '.join(filter(None, row[0:last])),
                        ', '.join(filter(None, [driver, driver_annotation]))
                    )
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

        port = data['port']
        if port:
            adv_config = await self.middleware.call('system.advanced.config')
            serial_port = os.path.join('/dev', adv_config['serialport'])
            if adv_config['serialconsole'] and serial_port == port:
                verrors.add(
                    f'{schema}.port',
                    'UPS port must be different then the port specified for '
                    'serial port for console in system advanced settings'
                )

        identifier = data['identifier']
        if identifier:
            if not re.search(r'^[a-z0-9\.\-_]+$', identifier, re.I):
                verrors.add(
                    f'{schema}.identifier',
                    'Use alphanumeric characters, ".", "-" and "_"'
                )

        for field in ['monpwd', 'monuser']:
            if re.search(r'[ #]', data[field], re.I):
                verrors.add(f'{schema}.{field}', 'Spaces or number signs are not allowed.')

        mode = data.get('mode')
        if mode == 'MASTER':
            for field in filter(
                lambda f: not data[f],
                ['port', 'driver']
            ):
                verrors.add(
                    f'{schema}.{field}',
                    'This field is required'
                )
        else:
            if not data.get('remotehost'):
                verrors.add(
                    f'{schema}.remotehost',
                    'This field is required'
                )

        data['mode'] = data['mode'].lower()
        data['shutdown'] = data['shutdown'].lower()

        verrors.check()
        return data

    @api_method(UPSUpdateArgs, UPSUpdateResult)
    async def do_update(self, data):
        """
        Update UPS Service Configuration.

        `powerdown` when enabled, sets UPS to power off after shutting down the system.

        `nocommwarntime` is a value in seconds which makes UPS Service wait the specified seconds before alerting that
        the Service cannot reach configured UPS.

        `shutdowntimer` is a value in seconds which tells the Service to wait specified seconds for the UPS before
        initiating a shutdown. This only applies when `shutdown` is set to "BATT".

        `shutdowncmd` is the command which is executed to initiate a shutdown. It defaults to "poweroff".
        """
        config = await self.config()
        config.pop('complete_identifier')
        old_config = config.copy()
        config.update(data)
        config = await self.validate_data(config, 'ups_update')

        old_config['mode'] = old_config['mode'].lower()
        old_config['shutdown'] = old_config['shutdown'].lower()

        if len(set(old_config.items()) ^ set(config.items())) > 0:
            if config['identifier'] != old_config['identifier']:
                await self.dismiss_alerts()

            await self._update_service(old_config, config)

        return await self.config()

    @private
    async def alerts_mapping(self):
        return {
            'LOWBATT': 'UPSBatteryLow',
            'COMMBAD': 'UPSCommbad',
            'COMMOK': 'UPSCommok',
            'ONBATT': 'UPSOnBattery',
            'ONLINE': 'UPSOnline',
            'REPLBATT': 'UPSReplbatt'
        }

    @private
    async def dismiss_alerts(self):
        alerts = list((await self.alerts_mapping()).values())
        await self.middleware.call('alert.oneshot_delete', alerts)

    @private
    async def upssched_event(self, notify_type):
        config = await self.config()
        upsc_identifier = config['complete_identifier']
        cp = await run('upsc', upsc_identifier, check=False)
        if cp.returncode:
            stats_output = ''
            stderr = cp.stderr.decode(errors='ignore')
            if stderr not in self.LOGGED_ERRORS:
                self.LOGGED_ERRORS.append(stderr)
                self.logger.error('Failed to retrieve ups information: %s', stderr)
        else:
            stats_output = cp.stdout.decode()

        if RE_TEST_IN_PROGRESS.search(stats_output):
            self.logger.debug('Self test is in progress and %r notify event should be ignored', notify_type)
            return

        if notify_type.lower() == 'shutdown':
            # Before we start FSD with upsmon, lets ensure that ups is not ONLINE (OL).
            # There are cases where battery/charger issues can result in ups.status being "OL LB" at the
            # same time. This will ensure that we don't initiate a shutdown if ups is OL.
            ups_status = RE_UPS_STATUS.findall(stats_output)
            if ups_status and 'ol' in ups_status[0].lower():
                self.middleware.logger.debug(
                    f'Shutdown not initiated as ups.status ({ups_status[0]}) indicates '
                    f'{config["identifier"]} is ONLINE (OL).'
                )
            else:
                # if we shutdown the active node while the passive is still online
                # then we're just going to cause a failover event. Shut the passive down
                # first and then shut the active node down
                if await self.middleware.call('failover.licensed'):
                    if await self.middleware.call('failover.status') == 'MASTER':
                        try:
                            await self.middleware.call('failover.call_remote', 'ups.upssched_event', ['shutdown'])
                        except Exception:
                            self.logger.error('failed shutting down passive node', exc_info=True)

                await run('upsmon', '-c', 'fsd', check=False)

        elif 'notify' in notify_type.lower():
            # notify_type is expected to be of the following format
            # NOTIFY-EVENT i.e NOTIFY-LOWBATT
            notify_type = notify_type.split('-')[-1]

            # We would like to send alerts for the following events
            alert_mapping = await self.alerts_mapping()

            await self.dismiss_alerts()

            if notify_type in alert_mapping:
                # Send user with the notification event and details
                # We send the email in the following format ( inclusive line breaks )

                # UPS Statistics: 'ups'
                #
                # Statistics recovered:
                #
                # 1) Battery charge (percent)
                # battery.charge: 5
                #
                # 2) Remaining battery level when UPS switches to LB (percent)
                # battery.charge.low: 10
                #
                # 3) Battery runtime (seconds)
                # battery.runtime: 1860
                #
                # 4) Remaining battery runtime when UPS switches to LB (seconds)
                # battery.runtime.low: 900
                body = f'<br><br>UPS Statistics: {config["identifier"]!r}<br><br>'

                # Let's gather following stats
                data_points = {
                    'battery.charge': 'Battery charge (percent)',
                    'battery.charge.low': 'Battery level remaining (percent) when UPS switches to Low Battery (LB)',
                    'battery.charge.status': 'Battery charge status',
                    'battery.runtime': 'Battery runtime (seconds)',
                    'battery.runtime.low': 'Battery runtime remaining (seconds) when UPS switches to Low Battery (LB)',
                    'battery.runtime.restart': 'Minimum battery runtime (seconds) to allow UPS restart after power-off',
                }

                stats_output = (
                    await run('upsc', upsc_identifier, check=False)
                ).stdout
                recovered_stats = re.findall(
                    fr'({"|".join(data_points)}): (.*)',
                    '' if not stats_output else stats_output.decode()
                )

                if recovered_stats:
                    body += 'Statistics recovered:<br><br>'
                    # recovered_stats is expected to be a list in this format
                    # [('battery.charge', '5'), ('battery.charge.low', '10'), ('battery.runtime', '1860')]
                    for index, stat in enumerate(recovered_stats):
                        body += f'{index + 1}) {data_points[stat[0]]}<br> ' \
                                f'&nbsp;&nbsp;&nbsp; {stat[0]}: {stat[1]}<br><br>'
                else:
                    body += 'Statistics could not be recovered<br>'

                await self.middleware.call(
                    'alert.oneshot_create', alert_mapping[notify_type], {'ups': config['identifier'], 'body': body}
                )
        else:
            self.middleware.logger.debug(f'Unrecognized UPS notification event: {notify_type}')


async def setup(middleware):
    # Let's delete all UPS related alerts when starting middlewared ensuring we don't have any leftovers
    await middleware.call('ups.dismiss_alerts')
