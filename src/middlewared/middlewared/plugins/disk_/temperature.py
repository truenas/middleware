import asyncio
import os
import re
import subprocess
import time

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

        output = list(map(float, subprocess.check_output(
            ['rrdtool', 'graph', 'x', '--daemon', 'unix:/var/run/rrdcached.sock', '--start', f'-{days}d', '--end',
             'now'] + args,
            encoding='ascii',
        ).split()[1:]))  # The first line is `0x0`

        result = {}
        for disk, values in zip(disks, grouper(output, 3)):  # FIXME: `incomplete='strict' when we switch to python 3.10
            result[disk] = {
                'min': values[0],
                'max': values[1],
                'avg': values[2],
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
