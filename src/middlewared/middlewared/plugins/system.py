import asyncio
from datetime import datetime, date, timezone, timedelta
from middlewared.event import EventSource
from middlewared.schema import accepts, Bool, Datetime, Dict, Float, Int, List, returns, Str
from middlewared.service import CallError, no_auth_required, job, pass_app, private, Service, throttle
from middlewared.utils import Popen, run, start_daemon_thread, sw_buildtime, sw_version, sw_version_is_stable, osc
from middlewared.utils.license import LICENSE_ADDHW_MAPPING

import ntplib
import io
import os
import psutil
import re
import requests
import shutil
import socket
import subprocess
import hashlib
import tarfile
import textwrap
import time
import uuid

from licenselib.license import ContractType, Features, License
from pathlib import Path


SYSTEM_BOOT_ID = None
SYSTEM_FIRST_BOOT = False
# Flag telling whether the system completed boot and is ready to use
SYSTEM_READY = False
# Flag telling whether the system is shutting down
SYSTEM_SHUTTING_DOWN = False

CACHE_POOLS_STATUSES = 'system.system_health_pools'
FIRST_INSTALL_SENTINEL = '/data/first-boot'

RE_KDUMP_CONFIGURED = re.compile(r'current state\s*:\s*(ready to kdump)', flags=re.M)

DEBUG_MAX_SIZE = 30


def throttle_condition(middleware, app, *args, **kwargs):
    return app is None or (app and app.authenticated), None


class SystemService(Service):

    CPU_INFO = {
        'cpu_model': None,
        'core_count': None,
        'physical_core_count': None,
    }

    MEM_INFO = {
        'physmem_size': None,
    }

    BIRTHDAY_DATE = {
        'date': None,
    }

    HOST_ID = PRODUCT_TYPE = None

    class Config:
        cli_namespace = 'system'

    @private
    async def birthday(self):

        if self.BIRTHDAY_DATE['date'] is None:
            birth = (await self.middleware.call('datastore.config', 'system.settings'))['stg_birthday']
            if birth != datetime(1970, 1, 1):
                self.BIRTHDAY_DATE['date'] = birth

        return self.BIRTHDAY_DATE

    @private
    async def mem_info(self):

        if self.MEM_INFO['physmem_size'] is None:
            # physmem doesn't change after boot so cache the results
            self.MEM_INFO['physmem_size'] = psutil.virtual_memory().total

        return self.MEM_INFO

    @private
    async def first_boot(self):
        return SYSTEM_FIRST_BOOT

    @private
    async def cpu_info(self):

        """
        CPU info doesn't change after boot so cache the results
        """

        if self.CPU_INFO['cpu_model'] is None:
            self.CPU_INFO['cpu_model'] = osc.get_cpu_model()

        if self.CPU_INFO['core_count'] is None:
            self.CPU_INFO['core_count'] = psutil.cpu_count(logical=True)

        if self.CPU_INFO['physical_core_count'] is None:
            self.CPU_INFO['physical_core_count'] = psutil.cpu_count(logical=False)

        return self.CPU_INFO

    @private
    async def time_info(self):
        uptime_seconds = time.clock_gettime(time.CLOCK_MONOTONIC_RAW)
        current_time = time.time()

        return {
            'uptime_seconds': uptime_seconds,
            'uptime': str(timedelta(seconds=uptime_seconds)),
            'boot_time': datetime.fromtimestamp((current_time - uptime_seconds), timezone.utc),
            'datetime': datetime.fromtimestamp(current_time, timezone.utc),
        }

    @private
    async def hostname(self):
        return socket.gethostname()

    @accepts()
    @returns(Str('system_boot_identifier'))
    async def boot_id(self):
        """
        Returns an unique boot identifier.

        It is supposed to be unique every system boot.
        """
        return SYSTEM_BOOT_ID

    @accepts()
    @returns(Bool('system_ready'))
    async def ready(self):
        """
        Returns whether the system completed boot and is ready to use
        """
        return await self.middleware.call("system.state") != "BOOTING"

    @accepts()
    @returns(Str('system_state', enum=['SHUTTING_DOWN', 'READY', 'BOOTING']))
    async def state(self):
        """
        Returns system state:
        "BOOTING" - System is booting
        "READY" - System completed boot and is ready to use
        "SHUTTING_DOWN" - System is shutting down
        """
        if SYSTEM_SHUTTING_DOWN:
            return "SHUTTING_DOWN"
        if SYSTEM_READY:
            return "READY"
        return "BOOTING"



    @accepts()
    @returns(Str('system_host_identifier'))
    def host_id(self):
        """
        Retrieve a hex string that is generated based
        on the contents of the `/etc/hostid` file. This
        is a permanent value that persists across
        reboots/upgrades and can be used as a unique
        identifier for the machine.
        """
        if self.HOST_ID is None:
            with open('/etc/hostid', 'rb') as f:
                id = f.read().strip()
                if id:
                    self.HOST_ID = hashlib.sha256(id).hexdigest()

        return self.HOST_ID

    @no_auth_required
    @throttle(seconds=2, condition=throttle_condition)
    @accepts()
    @returns(Datetime('system_build_time'))
    @pass_app()
    async def build_time(self, app):
        """
        Retrieve build time of the system.
        """
        buildtime = sw_buildtime()
        return datetime.fromtimestamp(int(buildtime)) if buildtime else buildtime

    @accepts()
    @returns(Dict(
        'system_info',
        Str('version', required=True, title='TrueNAS Version'),
        Datetime('buildtime', required=True, title='TrueNAS build time'),
        Str('hostname', required=True, title='System host name'),
        Int('physmem', required=True, title='System physical memory'),
        Str('model', required=True, title='CPU Model'),
        Int('cores', required=True, title='CPU Cores'),
        Int('physical_cores', required=True, title='CPU Physical Cores'),
        List('loadavg', required=True),
        Str('uptime', required=True),
        Float('uptime_seconds', required=True),
        Str('system_serial', required=True, null=True),
        Str('system_product', required=True, null=True),
        Str('system_product_version', required=True, null=True),
        Dict('license', additional_attrs=True, null=True),  # TODO: Fill this in please
        Datetime('boottime', required=True),
        Datetime('datetime', required=True),
        Datetime('birthday', required=True, null=True),
        Str('timezone', required=True),
        Str('system_manufacturer', required=True, null=True),
        Bool('ecc_memory', required=True),
    ))
    async def info(self):
        """
        Returns basic system information.
        """
        time_info = await self.middleware.call('system.time_info')
        dmidecode = await self.middleware.call('system.dmidecode_info')
        cpu_info = await self.middleware.call('system.cpu_info')
        mem_info = await self.middleware.call('system.mem_info')
        birthday = await self.middleware.call('system.birthday')
        timezone_setting = (await self.middleware.call('datastore.config', 'system.settings'))['stg_timezone']

        return {
            'version': self.version(),
            'buildtime': await self.middleware.call('system.build_time'),
            'hostname': await self.middleware.call('system.hostname'),
            'physmem': mem_info['physmem_size'],
            'model': cpu_info['cpu_model'],
            'cores': cpu_info['core_count'],
            'physical_cores': cpu_info['physical_core_count'],
            'loadavg': list(os.getloadavg()),
            'uptime': time_info['uptime'],
            'uptime_seconds': time_info['uptime_seconds'],
            'system_serial': dmidecode['system-serial-number'] if dmidecode['system-serial-number'] else None,
            'system_product': dmidecode['system-product-name'] if dmidecode['system-product-name'] else None,
            'system_product_version': dmidecode['system-version'] if dmidecode['system-version'] else None,
            'license': await self.middleware.call('system.license'),
            'boottime': time_info['boot_time'],
            'datetime': time_info['datetime'],
            'birthday': birthday['date'],
            'timezone': timezone_setting,
            'system_manufacturer': dmidecode['system-manufacturer'] if dmidecode['system-manufacturer'] else None,
            'ecc_memory': dmidecode['ecc-memory'],
        }

    @private
    async def is_ix_hardware(self):
        product = (await self.middleware.call('system.dmidecode_info'))['system-product-name']
        return product is not None and product.startswith(('FREENAS-', 'TRUENAS-'))

    @private
    async def is_enterprise_ix_hardware(self):
        return await self.middleware.call('truenas.get_chassis_hardware') != 'TRUENAS-UNKNOWN'

    @private
    def get_synced_clock_time(self):
        """
        Will return synced clock time if ntpd has synced with ntp servers
        otherwise will return none
        """
        client = ntplib.NTPClient()
        try:
            response = client.request('localhost')
        except Exception:
            # Cannot connect to NTP server
            self.logger.error('Error while connecting to NTP server', exc_info=True)
        else:
            if response.version and response.leap != 3:
                # https://github.com/darkhelmet/ntpstat/blob/11f1d49cf4041169e1f741f331f65645b67680d8/ntpstat.c#L172
                # if leap second indicator is 3, it means that the clock has not been synchronized
                return datetime.fromtimestamp(response.tx_time, timezone.utc)

    @accepts(Str('feature', enum=['DEDUP', 'FIBRECHANNEL', 'VM']))
    @returns(Bool('feature_enabled'))
    async def feature_enabled(self, name):
        """
        Returns whether the `feature` is enabled or not
        """
        is_core = (await self.middleware.call('system.product_type')) == 'CORE'
        if name == 'FIBRECHANNEL' and is_core:
            return False
        elif is_core:
            return True
        license = await self.middleware.call('system.license')
        if license and name in license['features']:
            return True
        return False

    @accepts(Dict('system-reboot', Int('delay', required=False), required=False))
    @returns()
    @job()
    async def reboot(self, job, options):
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
            await asyncio.sleep(delay)

        await Popen(['/sbin/shutdown', '-r', 'now'])

    @accepts(Dict('system-shutdown', Int('delay', required=False), required=False))
    @returns()
    @job()
    async def shutdown(self, job, options):
        """
        Shuts down the operating system.

        An "added" event of name "system" and id "shutdown" is emitted when shutdown is initiated.
        """
        if options is None:
            options = {}

        delay = options.get('delay')
        if delay:
            await asyncio.sleep(delay)

        await Popen(['/sbin/poweroff'])

    @private
    @job(lock='system.debug_generate')
    def debug_generate(self, job):
        """
        Generate system debug file.

        Result value will be the absolute path of the file.
        """
        system_dataset_path = self.middleware.call_sync('systemdataset.config')['path']
        if system_dataset_path is not None:
            direc = os.path.join(system_dataset_path, 'ixdiagnose')
        else:
            direc = '/var/tmp/ixdiagnose'
        dump = os.path.join(direc, 'ixdiagnose.tgz')

        # Be extra safe in case we have left over from previous run
        if os.path.exists(direc):
            shutil.rmtree(direc)

        cp = subprocess.Popen(
            ['ixdiagnose', '-d', direc, '-s', '-F', '-p'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            encoding='utf-8', errors='ignore', bufsize=1,
        )

        for line in iter(cp.stdout.readline, ''):
            line = line.rstrip()

            if line.startswith('**') and '%: ' in line:
                percent, desc = line.split('%: ', 1)
                try:
                    percent = int(percent.split()[-1])
                except ValueError:
                    continue
                job.set_progress(percent, desc)
        _, stderr = cp.communicate()

        if cp.returncode != 0:
            raise CallError(f'Failed to generate debug file: {stderr}')

        job.set_progress(100, 'Debug generation finished')

        return dump

    @accepts()
    @returns()
    @job(lock='system.debug', pipes=['output'])
    def debug(self, job):
        """
        Job to stream debug file.

        This method is meant to be used in conjuntion with `core.download` to get the debug
        downloaded via HTTP.
        """
        job.set_progress(0, 'Generating debug file')
        debug_job = self.middleware.call_sync(
            'system.debug_generate',
            job_on_progress_cb=lambda encoded: job.set_progress(int(encoded['progress']['percent'] * 0.9),
                                                                encoded['progress']['description'])
        )

        standby_debug = None
        if self.middleware.call_sync('failover.licensed'):
            try:
                standby_debug = self.middleware.call_sync(
                    'failover.call_remote', 'system.debug_generate', [], {'job': True}
                )
            except Exception:
                self.logger.warn('Failed to get debug from standby node', exc_info=True)
            else:
                remote_ip = self.middleware.call_sync('failover.remote_ip')
                url = self.middleware.call_sync(
                    'failover.call_remote', 'core.download', ['filesystem.get', [standby_debug], 'debug.txz'],
                )[1]

                url = f'http://{remote_ip}:6000{url}'
                # no reason to honor proxy settings in this
                # method since we're downloading the debug
                # archive directly across the heartbeat
                # interface which is point-to-point
                proxies = {'http': '', 'https': ''}
                standby_debug = io.BytesIO()
                with requests.get(url, stream=True, proxies=proxies) as r:
                    for i in r.iter_content(chunk_size=1048576):
                        if standby_debug.tell() > DEBUG_MAX_SIZE * 1048576:
                            raise CallError(f'Standby debug file is bigger than {DEBUG_MAX_SIZE}MiB.')
                        standby_debug.write(i)

        debug_job.wait_sync()
        if debug_job.error:
            raise CallError(debug_job.error)

        job.set_progress(90, 'Preparing debug file for streaming')

        if standby_debug:
            # Debug file cannot be big on HA because we put both debugs in memory
            # so they can be downloaded at once.
            try:
                if os.stat(debug_job.result).st_size > DEBUG_MAX_SIZE * 1048576:
                    raise CallError(f'Debug file is bigger than {DEBUG_MAX_SIZE}MiB.')
            except FileNotFoundError:
                raise CallError('Debug file was not found, try again.')

            network = self.middleware.call_sync('network.configuration.config')
            node = self.middleware.call_sync('failover.node')

            tario = io.BytesIO()
            with tarfile.open(fileobj=tario, mode='w') as tar:

                if node == 'A':
                    my_hostname = network['hostname']
                    remote_hostname = network['hostname_b']
                else:
                    my_hostname = network['hostname_b']
                    remote_hostname = network['hostname']

                tar.add(debug_job.result, f'{my_hostname}.txz')

                tarinfo = tarfile.TarInfo(f'{remote_hostname}.txz')
                tarinfo.size = standby_debug.tell()
                standby_debug.seek(0)
                tar.addfile(tarinfo, fileobj=standby_debug)

            tario.seek(0)
            shutil.copyfileobj(tario, job.pipes.output.w)
        else:
            with open(debug_job.result, 'rb') as f:
                shutil.copyfileobj(f, job.pipes.output.w)
        job.pipes.output.w.close()


async def _update_birthday(middleware):
    while True:
        birthday = await middleware.call('system.get_synced_clock_time')
        if birthday:
            middleware.logger.debug('Updating birthday data')
            # update db with new birthday
            settings = await middleware.call('datastore.config', 'system.settings')
            await middleware.call(
                'datastore.update', 'system.settings', settings['id'], {'stg_birthday': birthday}, {'ha_sync': False}
            )
            break
        else:
            await asyncio.sleep(300)


async def _event_system(middleware, event_type, args):

    global SYSTEM_READY
    global SYSTEM_SHUTTING_DOWN
    if args['id'] == 'ready':
        SYSTEM_READY = True

        # Check if birthday is already set
        birthday = await middleware.call('system.birthday')
        if birthday is None:
            # try to set birthday in background
            asyncio.ensure_future(_update_birthday(middleware))

        if (await middleware.call('system.advanced.config'))['kdump_enabled']:
            cp = await run(['kdump-config', 'status'], check=False)
            if cp.returncode:
                middleware.logger.error('Failed to retrieve kdump-config status: %s', cp.stderr.decode())
            else:
                if not RE_KDUMP_CONFIGURED.findall(cp.stdout.decode()):
                    await middleware.call('alert.oneshot_create', 'KdumpNotReady', None)
                else:
                    await middleware.call('alert.oneshot_delete', 'KdumpNotReady', None)
        else:
            await middleware.call('alert.oneshot_delete', 'KdumpNotReady', None)

        if await middleware.call('system.first_boot'):
            asyncio.ensure_future(middleware.call('usage.firstboot'))

    if args['id'] == 'shutdown':
        SYSTEM_SHUTTING_DOWN = True


class SystemHealthEventSource(EventSource):

    """
    Notifies of current system health which include statistics about consumption of memory and CPU, pools and
    if updates are available. An integer `delay` argument can be specified to determine the delay
    on when the periodic event should be generated.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._check_update = None
        start_daemon_thread(target=self.check_update)

    def check_update(self):
        while not self._cancel_sync.is_set():
            try:
                self._check_update = self.middleware.call_sync('update.check_available')['status']
            except Exception:
                self.middleware.logger.warn(
                    'Failed to check available update for system.health event', exc_info=True,
                )
            finally:
                self._cancel_sync.wait(timeout=60 * 60 * 24)

    def pools_statuses(self):
        return {
            p['name']: {'status': p['status']}
            for p in self.middleware.call_sync('pool.query')
        }

    def run_sync(self):

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

        cp_time = psutil.cpu_times()
        cp_old = cp_time

        while not self._cancel_sync.is_set():
            time.sleep(delay)

            cp_time = psutil.cpu_times()
            cp_diff = type(cp_time)(*map(lambda x: x[0] - x[1], zip(cp_time, cp_old)))
            cp_old = cp_time

            cpu_percent = round(((sum(cp_diff) - cp_diff.idle) / sum(cp_diff)) * 100, 2)

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


async def firstboot(middleware):
    global SYSTEM_FIRST_BOOT
    if os.path.exists(FIRST_INSTALL_SENTINEL):
        SYSTEM_FIRST_BOOT = True
        # Delete sentinel file before making clone as we
        # we do not want the clone to have the file in it.
        os.unlink(FIRST_INSTALL_SENTINEL)

        if await middleware.call('system.is_enterprise'):
            config = await middleware.call('datastore.config', 'system.advanced')
            await middleware.call('datastore.update', 'system.advanced', config['id'], {'adv_autotune': True})

        # Creating pristine boot environment from the "default"
        initial_install_be = 'Initial-Install'
        middleware.logger.info('Creating %r boot environment...', initial_install_be)
        activated_be = await middleware.call('bootenv.query', [['activated', '=', True]], {'get': True})
        try:
            await middleware.call('bootenv.create', {'name': initial_install_be, 'source': activated_be['realname']})
        except Exception:
            middleware.logger.error('Failed to create initial boot environment', exc_info=True)
        else:
            boot_pool = await middleware.call('boot.pool_name')
            cp = await run(
                'zfs', 'set', f'{"zectl" if osc.IS_LINUX else "beadm"}:keep=True',
                os.path.join(boot_pool, 'ROOT/Initial-Install')
            )
            if cp.returncode != 0:
                middleware.logger.error(
                    'Failed to set keep attribute for Initial-Install boot environment: %s', cp.stderr.decode()
                )


async def hook_license_update(middleware, prev_product_type, *args, **kwargs):
    if prev_product_type != 'ENTERPRISE' and await middleware.call('system.product_type') == 'ENTERPRISE':
        await middleware.call('system.advanced.update', {'autotune': True})


async def setup(middleware):
    global SYSTEM_BOOT_ID, SYSTEM_READY

    SYSTEM_BOOT_ID = str(uuid.uuid4())

    middleware.event_register('system', textwrap.dedent('''\
        Sent on system state changes.

        id=ready -- Finished boot process\n
        id=reboot -- Started reboot process\n
        id=shutdown -- Started shutdown process'''))

    if os.path.exists("/tmp/.bootready"):
        SYSTEM_READY = True
    else:
        await firstboot(middleware)

    settings = await middleware.call('system.general.config')
    await middleware.call('core.environ_update', {'TZ': settings['timezone']})

    middleware.logger.debug(f'Timezone set to {settings["timezone"]}')

    await middleware.call('system.general.set_language')
    await middleware.call('system.general.set_crash_reporting')

    middleware.event_subscribe('system', _event_system)
    middleware.register_event_source('system.health', SystemHealthEventSource)

    CRASH_DIR = '/data/crash'
    os.makedirs(CRASH_DIR, exist_ok=True)
    os.chmod(CRASH_DIR, 0o775)

    await middleware.call('sysctl.set_zvol_volmode', 2)

    middleware.register_hook('system.post_license_update', hook_license_update)
