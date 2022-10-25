import asyncio
import os
import re
import subprocess
import time
import math
import pathlib
import contextlib

import pyudev
import async_timeout

from middlewared.common.smart.smartctl import SMARTCTL_POWERMODES
from middlewared.schema import Bool, Dict, Int, returns
from middlewared.service import accepts, List, private, Ref, Service, Str
from middlewared.utils.asyncio_ import asyncio_map
from middlewared.utils.itertools import grouper


def get_temperature(stdout):
    # ataprint.cpp

    data = {}
    for s in re.findall(r'^((190|194) .+)', stdout, re.M):
        s = s[0].split()
        try:
            data[s[1]] = int(s[9])
        except (IndexError, ValueError):
            pass
    for k in ['Temperature_Celsius', 'Temperature_Internal', 'Drive_Temperature',
              'Temperature_Case', 'Case_Temperature', 'Airflow_Temperature_Cel']:
        if k in data:
            return data[k]

    reg = re.search(r'194\s+Temperature_Celsius[^\n]*', stdout, re.M)
    if reg:
        return int(reg.group(0).split()[9])

    # nvmeprint.cpp

    reg = re.search(r'Temperature:\s+([0-9]+) Celsius', stdout, re.M)
    if reg:
        return int(reg.group(1))

    reg = re.search(r'Temperature Sensor [0-9]+:\s+([0-9]+) Celsius', stdout, re.M)
    if reg:
        return int(reg.group(1))

    # scsiprint.cpp

    reg = re.search(r'Current Drive Temperature:\s+([0-9]+) C', stdout, re.M)
    if reg:
        return int(reg.group(1))


class DiskService(Service):
    cache = {}

    @private
    async def disks_for_temperature_monitoring(self):
        return [
            disk['name']
            for disk in await self.middleware.call(
                'disk.query',
                [
                    ['name', '!=', None],
                    ['togglesmart', '=', True],
                    # Polling for disk temperature does not allow them to go to sleep automatically
                    ['hddstandby', '=', 'ALWAYS ON'],
                ]
            )
        ]

    @accepts(
        Str('name'),
        Dict(
            'options',
            Int('cache', default=None, null=True),
            Str('powermode', enum=SMARTCTL_POWERMODES, default=SMARTCTL_POWERMODES[0]),
        ),
        deprecated=[
            (
                lambda args: len(args) == 2 and isinstance(args[1], str),
                lambda name, powermode: [name, {'powermode': powermode}],
            ),
        ],
    )
    @returns(Int('temperature', null=True))
    async def temperature(self, name, options):
        """
        Returns temperature for device `name` using specified S.M.A.R.T. `powermode`. If `cache` is not null
        then the last cached within `cache` seconds value is used.
        """
        if options['cache'] is not None:
            if cached := self.cache.get(name):
                temperature, cache_time = cached
                if cache_time > time.monotonic() - options['cache']:
                    return temperature

        temperature = await self.middleware.call('disk.temperature_uncached', name, options['powermode'])

        self.cache[name] = (temperature, time.monotonic())
        return temperature

    @private
    async def temperature_uncached(self, name, powermode):
        output = await self.middleware.call('disk.smartctl', name, ['-a', '-n', powermode.lower()], {'silent': True})
        if output is not None:
            return get_temperature(output)

    @private
    async def reset_temperature_cache(self):
        self.cache = {}

    @accepts(
        List('names', items=[Str('name')]),
        Dict(
            'options',
            # A little less than collectd polling interval of 300 seconds to avoid returning old value when polling
            # occurs in 299.9 seconds.
            Int('cache', default=290, null=True),
            Bool('only_cached', default=False),
            Str('powermode', enum=SMARTCTL_POWERMODES, default=SMARTCTL_POWERMODES[0]),
        ),
        deprecated=[
            (
                lambda args: len(args) == 2 and isinstance(args[1], str),
                lambda name, powermode: [name, {'powermode': powermode}],
            ),
        ],
    )
    @returns(Dict('disks_temperatures', additional_attrs=True))
    async def temperatures(self, names, options):
        """
        Returns temperatures for a list of devices (runs in parallel).
        See `disk.temperature` documentation for more details.
        If `only_cached` is specified then this method only returns disk temperatures that exist in cache.
        """
        if len(names) == 0:
            names = await self.disks_for_temperature_monitoring()

        if options.pop('only_cached'):
            return {
                disk: temperature
                for disk, (temperature, cache_time) in self.cache.items()
                if (
                    disk in names and
                    cache_time > time.monotonic() - 610  # Double collectd polling interval + a little bit
                )
            }

        async def temperature(name):
            try:
                async with async_timeout.timeout(15):
                    return await self.middleware.call('disk.temperature', name, options)
            except asyncio.TimeoutError:
                return None

        return dict(zip(names, await asyncio_map(temperature, names, 8)))

    @private
    def read_sata_or_sas_disk_temps(self, disks):
        rv = {}
        with contextlib.suppress(FileNotFoundError):
            for i in pathlib.Path('/var/lib/smartmontools').iterdir():
                # TODO: throw this into multiple threads since we're reading data from disk
                # to make this really go brrrrr (even though it only takes ~0.2 seconds on 439 disk system)
                if i.is_file() and i.suffix == '.csv':
                    if serial := next((k for k in disks if i.as_posix().find(k) != -1), None):
                        with open(i.as_posix()) as f:
                            for line in f:
                                # iterate to the last line in the file without loading all of it
                                # into memory since `smartd` could have written 1000's (or more)
                                # of lines to the file
                                pass

                            if (ft := line.split('\t')) and (temp := list(filter(lambda x: 'temperature' in x, ft))):
                                try:
                                    temp = temp[-1].split(';')[1]
                                except IndexError:
                                    continue
                                else:
                                    if temp.isdigit():
                                        rv[disks[serial]] = int(temp)

        return rv

    @private
    def read_nvme_temps(self, disks):
        # we store nvme disks in db with their namespaces (i.e. nvme1n1, nvme2n1, etc)
        # but the hwmon sysfs sensors structure references the nvme devices via nvme1, nvme2
        # so we simply take first 5 chars so they map correctly
        nvme_disks = {v[:5]: v for v in disks.values() if v.startswith('nvme')}
        rv = {}
        ctx = pyudev.Context()
        for i in filter(lambda x: x.parent.sys_name in nvme_disks, ctx.list_devices(subsystem='hwmon')):
            if temp := i.attributes.get('temp1_input'):
                try:
                    # https://www.kernel.org/doc/Documentation/hwmon/sysfs-interface
                    # temperature is reported in millidegree celsius so must convert back to celsius
                    # we also round to nearest whole number for backwards compatbility
                    rv[nvme_disks[i.parent.sys_name]] = round(int(temp.decode()) * 0.001)
                except Exception:
                    # if this fails the caller of this will subprocess out to smartctl and try to
                    # get the temperature for the drive so dont crash here
                    continue

        return rv

    @private
    def read_temps(self):
        """
        The main consumer of this endpoint is the disktemp.py collectd python plugin
        which polls and calls this method every 300 seconds (5 mins). The way we configure
        the smartd.conf, the temperature will be written to disk in csv file format for each
        drive. However, smartd only supports writing temp information for sata/sas drives at
        the moment. Luckily, the kernel (via the hwmon interface) reports nvme drive temperatures
        (if the nvme drive supports it). This means we can get all drive temperatures quite quickly.
        However, if we can't get a drive temperature using these methods for whatever reason then
        we will fall back to subprocessing out to smartctl and trying to parse the temperature.
        """
        disks = {
            i['serial']: i['name'] for i in self.middleware.call_sync('datastore.query', 'storage.disk', [
                ['serial', '!=', ''],
                ['togglesmart', '=', True],
                ['hddstandby', '=', 'Always On'],
            ], {'prefix': 'disk_'})
        }
        temps = self.read_sata_or_sas_disk_temps(disks)
        temps.update(self.read_nvme_temps(disks))

        for disk in set(disks.values()) - set(temps.keys()):
            # try to subprocess and run smartctl for any disk that we didn't get the temp
            # for using the much quicker methods
            temps.update({disk: self.middleware.call_sync('disk.temperature_uncached', disk, 'never')})

        return temps

    @private
    def get_temp_value(self, value):
        if math.isnan(value):
            value = None
        return value

    @accepts(List('names', items=[Str('name')]), Int('days'))
    @returns(Dict('temperatures', additional_attrs=True))
    def temperature_agg(self, names, days):
        """
        Returns min/max/avg temperature for `names` disks for the last `days` days.
        """
        disks = []
        args = []
        for name in names:
            path = f'/var/db/collectd/rrd/localhost/disktemp-{name}/temperature.rrd'
            if not os.path.exists(path):
                continue

            disks.append(name)
            for DEF, VDEF in [('MIN', 'MINIMUM'), ('MAX', 'MAXIMUM'), ('AVERAGE', 'AVERAGE')]:
                args.extend([
                    f'DEF:{name}{DEF}=/var/db/collectd/rrd/localhost/disktemp-{name}/temperature.rrd:value:{DEF}',
                    f'VDEF:v{name}{DEF}={name}{DEF},{VDEF}',
                    f'PRINT:v{name}{DEF}:%lf',
                ])

        output = list(map(float, subprocess.run(
            ['rrdtool', 'graph', 'x', '--daemon', 'unix:/var/run/rrdcached.sock', '--start', f'-{days}d', '--end',
             'now'] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            encoding='ascii',
        ).stdout.split()[1:]))  # The first line is `0x0`

        result = {}
        for disk, values in zip(disks, grouper(output, 3)):  # FIXME: `incomplete='strict' when we switch to python 3.10
            result[disk] = {
                'min': self.get_temp_value(values[0]),
                'max': self.get_temp_value(values[1]),
                'avg': self.get_temp_value(values[2]),
            }

        return result

    @accepts(List('names', items=[Str('name')]))
    @returns(Ref('alert'))
    async def temperature_alerts(self, names):
        """
        Returns existing temperature alerts for specified disk `names.`
        """
        devices = {f'/dev/{name}' for name in names}
        alerts = await self.middleware.call('alert.list')
        return [
            alert for alert in alerts
            if (
                alert['klass'] == 'SMART' and
                alert['args']['device'] in devices and
                'temperature' in alert['args']['message'].lower()
            )
        ]
