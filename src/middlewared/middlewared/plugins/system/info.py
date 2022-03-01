import hashlib
import ntplib
import os
import psutil
import re
import socket
import time

from datetime import datetime, timedelta, timezone

from middlewared.schema import accepts, Bool, Datetime, Dict, Float, Int, List, returns, Str
from middlewared.service import no_auth_required, pass_app, private, Service, throttle
from middlewared.utils import sw_buildtime

DEBUG_MAX_SIZE = 30
RE_CPU_MODEL = re.compile(r'^model name\s*:\s*(.*)', flags=re.M)


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
    def get_cpu_model(self):
        with open('/proc/cpuinfo', 'r') as f:
            model = RE_CPU_MODEL.search(f.read())
            return model.group(1) if model else None

    @private
    async def cpu_info(self):
        """
        CPU info doesn't change after boot so cache the results
        """

        if self.CPU_INFO['cpu_model'] is None:
            self.CPU_INFO['cpu_model'] = await self.middleware.call('system.get_cpu_model')

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
            'version': await self.middleware.call('system.version'),
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
