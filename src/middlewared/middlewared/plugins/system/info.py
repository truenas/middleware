import hashlib
import os
import socket
import time

from datetime import datetime, timedelta, timezone

from middlewared.api import api_method
from middlewared.api.current import SystemHostIdArgs, SystemHostIdResult, SystemInfoArgs, SystemInfoResult
from middlewared.service import no_authz_required, private, Service
from middlewared.utils import sw_buildtime
from middlewared.utils.cpu import cpu_info


class SystemService(Service):
    HOST_ID = None

    class Config:
        cli_namespace = 'system'

    @private
    def mem_info(self):
        result = {'physmem_size': None}
        try:
            with open('/proc/meminfo') as f:
                for line in filter(lambda x: x.find('MemTotal') != -1, f):
                    fields = line.split()
                    # procfs reports in kB
                    result['physmem_size'] = int(fields[1]) * 1024
        except (FileNotFoundError, ValueError, IndexError):
            pass

        return result

    @private
    async def cpu_info(self):
        """CPU info could change after boot, but we
        cache it since hot-plugging cpus is something
        we've not accounted for."""
        return cpu_info()

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
    async def hostname(self) -> str:
        return socket.gethostname()

    @api_method(SystemHostIdArgs, SystemHostIdResult, roles=['READONLY_ADMIN'])
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
                id_ = f.read().strip()
                if id_:
                    self.HOST_ID = hashlib.sha256(id_).hexdigest()

        return self.HOST_ID

    @private
    async def build_time(self):
        """Retrieve build time of the system."""
        # NOTE: at time of writing, UI team is using this value
        # for the "copyright" section
        buildtime = sw_buildtime()
        return datetime.fromtimestamp(int(buildtime)) if buildtime else buildtime

    @api_method(SystemInfoArgs, SystemInfoResult, roles=['READONLY_ADMIN'])
    async def info(self):
        """
        Returns basic system information.
        """
        time_info = await self.time_info()
        dmidecode = await self.middleware.call('system.dmidecode_info')
        cpu_info = await self.cpu_info()
        mem_info = await self.middleware.run_in_thread(self.mem_info)
        timezone_setting = (await self.middleware.call('datastore.config', 'system.settings'))['stg_timezone']

        return {
            'version': await self.middleware.call('system.version_short'),
            'buildtime': await self.build_time(),
            'hostname': await self.hostname(),
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
        threshold = 300.0  # seconds (Microsoft AD is 5mins, so if it's good enough for them, good enough for us)
        for ntp in filter(lambda x: x['active'], self.middleware.call_sync('system.ntpserver.peers')):
            if abs(ntp['offset']) <= threshold:
                return datetime.now(timezone.utc)
